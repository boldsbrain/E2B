from typing import (
    List,
    Tuple,
    List,
    Any,
    Dict,
    Optional,
)
import subprocess

from pydantic import BaseModel
from langchain.llms.openai import OpenAIChat, OpenAI
from langchain.chat_models import ChatOpenAI
from langchain.callbacks.base import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.agents import AgentExecutor
from langchain.tools import BaseTool

# from codegen.tools.documentation import ReadDocumentation
# from codegen.env import EnvVar
# from codegen.js_agent import create_js_agent
# from codegen.prompt import PREFIX, SUFFIX, FORMAT_INSTRUCTIONS
# from codegen.tools.playground import create_playground_tools
# from database import Database

# from codegen.tools.playground import create_playground_tools
from codegen.env import EnvVar
from codegen.agent import CodegenAgent
from codegen.prompt import (
    PREFIX,
    SUFFIX,
    FORMAT_INSTRUCTIONS,
    HUMAN_INSTRUCTIONS_PREFIX,
    HUMAN_INSTRUCTIONS_SUFFIX,
)


class InvalidTool(BaseTool):
    name = "InvalidTool"
    description = "Do not use this tool! It is for human system admin only!"

    def _run(self, err: str) -> str:
        return err

    async def _arun(self, err: str) -> str:
        return err


class OutputFinalCode(BaseTool):
    name = "OutputFinalCode"
    description = "This is the last tool you would use. You use it when you know the final server code and you want to output it. The input should be the final server code that does what the user required."

    def _run(self, final_code: str) -> str:
        return final_code

    async def _arun(self, final_code: str) -> str:
        return NotImplementedError("OutputFinalCode does not support async")


class WriteCodeToFile(BaseTool):
    name = "WriteCodeToFile"
    description = """Writes code to the index.js file. The input should be the code to be written."""

    def _run(self, code: str) -> str:
        print(f"Writing code to file: \n{code}")
        with open(
            "/Users/vasekmlejnsky/Developer/nodejs-express-server/index.js", "w"
        ) as f:
            f.write(
                f"""
            import {{ createRequire }} from "module";
            const require = createRequire(import.meta.url);
            {code}"""
            )
        return "wrote code to index.js"

    async def _arun(self, err: str) -> str:
        return NotImplementedError("WriteCodeToFile does not support async")


class DeployCode(BaseTool):
    name = "DeployCode"
    description = """Deploys the code."""

    def _run(self, empty: str) -> str:
        print("Deploying...")
        p = subprocess.Popen(
            ["git", "add", "."],
            cwd="/Users/vasekmlejnsky/Developer/nodejs-express-server",
        )
        p.wait()
        p = subprocess.Popen(
            ["git", "commit", "-m", "Deploy"],
            cwd="/Users/vasekmlejnsky/Developer/nodejs-express-server",
        )
        p.wait()
        p = subprocess.Popen(
            [
                "git",
                "push",
            ],
            cwd="/Users/vasekmlejnsky/Developer/nodejs-express-server",
        )
        p.wait()
        return f"deployed server"

    async def _arun(self, empty: str) -> str:
        return NotImplementedError("DeployCode does not support async")


#     testing_instructions = """Here are your instructions:
# 1. Extract `email` from the incoming POST request.
# 2. If there's no email, respond back with an error.
# 3. Otherwise, respond back with the part of the email before the '@' sign.
# 4. Generate the full required server code and make sure it starts without any errors.
# 5. Test that the generated server from the previous step behaves as is required by making mock `curl` requests to the server.
# 6. Once all works without any bugs and errors, write the code to the file.
# 7. Deploy the code.
# """
class Codegen(BaseModel):
    agent: Optional[CodegenAgent]
    agent_executor: Optional[AgentExecutor]
    llm = ChatOpenAI(
        streaming=True,
        temperature=0,
        max_tokens=2056,
        verbose=True,
        callback_manager=CallbackManager([StreamingStdOutCallbackHandler()]),
    )
    input_variables = ["input", "agent_scratchpad", "method"]
    tools = [
        # InvalidTool(),
        # OutputFinalCode(),
        WriteCodeToFile(),
        DeployCode(),
    ]

    @classmethod
    def from_playground_tools(cls, playground_tools: Tuple[List[Any]]):
        c = cls()

        # Create CodegenAgent and its executor
        c.agent = CodegenAgent.from_llm_and_tools(
            llm=c.llm,
            tools=[
                *playground_tools,
                *c.tools,
            ],
            prefix=PREFIX,
            suffix=SUFFIX,
            format_instructions=FORMAT_INSTRUCTIONS,
            input_variables=c.input_variables,
        )
        c.agent_executor = AgentExecutor.from_agent_and_tools(
            agent=c.agent,
            tools=[
                *playground_tools,
                *c.tools,
            ],
            verbose=True,
        )

        return c

    def generate(
        self,
        envs: List[EnvVar],
        route: str,
        method: str,
        blocks: List[Dict],
    ):
        input_vars = {
            "route": route,
            "method": method,
        }
        instructions = "Here are the instructions:"
        inst_idx = 0

        # Append the premade prefix instructions.
        for instruction in HUMAN_INSTRUCTIONS_PREFIX:
            inst_idx += 1

            values = []
            # Extract the correct values from `input_vars` based on the keys.
            for k, v in input_vars.items():
                if k in instruction["variables"]:
                    values.append(v)

            # Use the values to format the instruction string.
            inst = instruction["content"].format(*values)
            instructions = instructions + "\n" + f"{inst_idx}. {inst}"

        for block in blocks:
            if block.get("type") == "Basic":
                inst_idx += 1
                instructions = instructions + "\n" + f"{inst_idx}. " + block["prompt"]

        # Append the premade suffix instructions.
        for inst in HUMAN_INSTRUCTIONS_SUFFIX:
            inst_idx += 1
            instructions = instructions + "\n" + f"{inst_idx}. {inst}"

        self.agent_executor.run(
            agent_scratchpad="",
            # input=testing_instructions
            input=instructions,
            method=method,
        )


# def generate_req_handler(
#     db: Database,
#     run_id: str,
#     blocks: List[Dict],
#     method: str,
#     route: str,
#     envs: List[EnvVar],
# ):
#     request_body_blocks = [
#         block for block in blocks if block.get("type") == "RequestBody"
#     ]
#     request_body_template = (
#         request_body_blocks[0]["prompt"] if len(request_body_blocks) > 0 else None
#     )
#     playground_tools, playground = create_playground_tools(
#         envs=envs,
#         route=route,
#         method=method,
#         request_body_template=request_body_template,
#     )

#     steps = ""
#     for idx, block in enumerate(blocks):
#         if block.get("type") == "Basic":
#             steps = steps + "\n" + "{}. ".format(idx + 1) + block["prompt"] + "\n"
#     tool_names = ["InstallNPMDependencies", "RunJavaScriptCode"]
#     prefix = PREFIX.format(
#         method=method,
#         tool_names=tool_names,
#         steps=steps,
#         request_body=request_body_template,
#     )
#     format_instructions = FORMAT_INSTRUCTIONS.format(
#         tool_names=tool_names,
#     )
#     executor = create_js_agent(
#         db=db,
#         run_id=run_id,
#         llm=OpenAI(temperature=0, max_tokens=1000),
#         # llm=OpenAI(temperature=0, model_name='code-davinci-002', max_tokens=1000),
#         # llm=OpenAIChat(temperature=0, max_tokens=1000),
#         tools=[
#             # ReadDocumentation()
#             *playground_tools,
#         ],
#         verbose=True,
#         prefix=prefix,
#         format_instructions=format_instructions,
#     )

#     # Convert env vars to Javascript comments, each on its on line for each env var.
#     # envs_str = ""
#     # for env in envs:
#     #     envs_str += f'// const {env["key"]} = `env.{env["key"]}`\n'

#     # prompt = PREFIX.format(
#     #     method=method, envs=envs_str, request_body=request_body_template
#     # )

#     # for idx, block in enumerate(blocks):
#     #     if block.get("type") == "Basic":
#     #         prompt = prompt + "\n" + "{}. ".format(idx + 1) + block["prompt"] + "\n"

#     # prompt = prompt + "\n" + SUFFIX.format(method=method)

#     # handler_code = executor.run(prompt).strip("`").strip()
#     handler_code = executor.run(f"Requirement:").strip("`").strip()
#     print("CODE")
#     print(handler_code)

#     playground.close()

#     return "", handler_code