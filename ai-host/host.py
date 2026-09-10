import os
import asyncio
from dotenv import load_dotenv
from google import genai
from google.genai import types
from mcp.client.streamable_http import streamable_http_client
from mcp.client.session import ClientSession        # <-- the session with .initialize()

load_dotenv()

gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MCP_URL = os.getenv("MCP_SERVER_URL")
WRITE_TOOLS = {"scale_gke_node_pool"}

def mcp_tools_to_gemini(mcp_tools):
    decls = []
    for t in mcp_tools:
        schema = dict(t.input_schema or {})
        schema.pop("$schema", None)
        schema.pop("additionalProperties", None)
        decls.append(types.FunctionDeclaration(
            name=t.name,
            description=t.description or "",
            parameters=schema,
        ))
    return [types.Tool(function_declarations=decls)]

async def main():
    # ONE connection path: transport yields (read, write); wrap in ClientSession
    async with streamable_http_client(MCP_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tool_list = (await session.list_tools()).tools
            gemini_tools = mcp_tools_to_gemini(tool_list)
            print(f"Connected. Tools: {[t.name for t in tool_list]}\n")

            chat = gemini.chats.create(
                model="gemini-3.7-flash",
                config=types.GenerateContentConfig(tools=gemini_tools),
            )

            print("Ask about your infrastructure ('quit' to exit).")
            while True:
                user_input = input("\nYou: ")
                if user_input.strip().lower() in {"quit", "exit"}:
                    break

                response = chat.send_message(user_input)

                while response.candidates[0].content.parts[0].function_call:
                    fc = response.candidates[0].content.parts[0].function_call
                    args = dict(fc.args)
                    print(f"[AI wants: {fc.name}  args={args}]")

                    # Human-in-the-loop gate on the EXECUTE phase of a write
                    if fc.name in WRITE_TOOLS and args.get("confirm_token"):
                        ok = input(f"⚠️  Approve EXECUTE {fc.name} {args}? (yes/no): ")
                        if ok.strip().lower() != "yes":
                            out = '{"status":"denied_by_human"}'
                            response = chat.send_message(
                                [types.Part.from_function_response(name=fc.name, response={"result": out})]
                            )
                            continue

                    result = await session.call_tool(fc.name, args)
                    out = result.content[0].text if result.content else ""

                    response = chat.send_message(
                        [types.Part.from_function_response(name=fc.name, response={"result": out})]
                    )

                print(f"\nGemini: {response.text}")


if __name__ == "__main__":
    asyncio.run(main())

