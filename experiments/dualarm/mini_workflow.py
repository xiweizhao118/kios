import json
import os

"""
currently not in use because of the proxy issue
"""

# * http proxy of the clash
# os.environ["http_proxy"] = "http://127.0.0.1:7890"
# os.environ["https_proxy"] = "http://127.0.0.1:7890"

# * MEGVII http_proxy transparent proxy
os.environ["http_proxy"] = "http://127.0.0.1:80"
os.environ["https_proxy"] = "https://127.0.0.1:443"

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_PROJECT"] = "kios_dualarm"

# os.environ["OPENAI_API_BASE"] = "https://gateway.ai.cloudflare.com/v1/08abfead72b07ac70f36a431a4a48c3d/bblab-gateway/openai"

from kios_bt_planning.kios_bt.bt_stewardship import BehaviorTreeStewardship
from kios_scene.scene_factory import SceneFactory
from kios_bt_planning.kios_bt.bt_factory import BehaviorTreeFactory
from kios_robot.robot_interface import RobotInterface
from kios_world.world_interface import WorldInterface

from dotenv import load_dotenv

from langchain_openai import ChatOpenAI

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser

from langchain.prompts.pipeline import PipelinePromptTemplate
from langchain.prompts.prompt import PromptTemplate

from langsmith import traceable

load_dotenv()

from kios_utils.pybt_test import generate_bt_stewardship, render_dot_tree

def render_bt(bt_json: dict):
    test_class = BehaviorTreeFactory()
    bt = test_class.from_json_to_simple_bt(bt_json)
    # bt = test_class.from_json_to_tree_root(bt_json)
    bt_stewardship = generate_bt_stewardship(bt)
    # bt_stewardship.setup(timeout=15)
    render_dot_tree(bt_stewardship)


def get_problem(problem_id: int) -> dict:
    file_dir = os.path.dirname(os.path.abspath(__file__))
    problem_dir = os.path.join(
        file_dir, "problem_set", f"problem_{str(problem_id).zfill(3)}.json"
    )
    with open(problem_dir, "r") as file:
        return json.load(file)


####################### dirs
current_dir = os.path.dirname(os.path.abspath(__file__))
scene_path = os.path.join(current_dir, "scene.json")
# bt_json_file_path = os.path.join(current_dir, "behavior_tree.json")
world_state_path = os.path.join(current_dir, "world_state.json")
domain_knowledge_path = os.path.join(current_dir, "domain_knowledge.txt")

####################### scene
with open(scene_path, "r") as file:
    scene_json_object = json.load(file)

# scene = SceneFactory().create_scene_from_json(scene_json_object)

####################### world
world_interface = WorldInterface()
with open(world_state_path, "r") as file:
    world_state_json = json.load(file)
    # world_interface.load_world_from_json(world_state_json)

####################### robot
robot_interface = RobotInterface(
    robot_address="127.0.0.1",
    robot_port=12000,
)
# robot_interface.setup_scene(scene)

####################### bt_factory
bt_factory = BehaviorTreeFactory(
    world_interface=world_interface,
    robot_interface=robot_interface,
)

####################### behavior_tree_stewardship
behavior_tree_stewardship = BehaviorTreeStewardship(
    behaviortree_factory=bt_factory,
    world_interface=world_interface,
    robot_interface=robot_interface,
)

# * kios data prompt dir
data_dir = os.environ.get("KIOS_DATA_DIR").format(username=os.getlogin())
print(data_dir)
prompt_dir_base = os.path.join(data_dir, "prompts")

folder_name = "dualarm3"
prompt_dir = os.path.join(prompt_dir_base, folder_name)

# * dualarm bt generation ppl
system_file = os.path.join(prompt_dir, "system.txt")
task_file = os.path.join(prompt_dir, "task.txt")
domain_file = os.path.join(prompt_dir, "domain.txt")
behaviortree_file = os.path.join(prompt_dir, "behaviortree.txt")
# example_file = os.path.join(prompt_dir, "dualarm/example.txt")
# output_format_file = os.path.join(prompt_dir, "dualarm/output_format.txt")
state_file = os.path.join(prompt_dir, "state.txt")
template_file = os.path.join(prompt_dir, "template.txt")
with open(template_file, "r") as f:
    template_ppt = PromptTemplate.from_template(f.read())
with open(task_file, "r") as f:
    task_ppt = PromptTemplate.from_template(f.read())
with open(system_file, "r") as f:
    system_ppt = PromptTemplate.from_template(f.read())
with open(domain_file, "r") as f:
    domain_ppt = PromptTemplate.from_template(f.read())
with open(state_file, "r") as f:
    state_ppt = PromptTemplate.from_template(f.read())
# with open(output_format_file, "r") as f:
    # output_format_ppt = PromptTemplate.from_template(f.read())
with open(behaviortree_file, "r") as f:
    ppt_tmp = PromptTemplate.from_template("{input}")
    behaviortree_ppt = ppt_tmp.partial(input=f.read())
# with open(example_file, "r") as f:
    # ppt_tmp = PromptTemplate.from_template("{input}")
    # example_ppt = ppt_tmp.partial(input=f.read())

full_template_ppt = ChatPromptTemplate.from_template(
    """{system}

    {task}

    {domain}

    {state}

    {behaviortree}

    {template}

    {format_instructions}
    """
)

parser = JsonOutputParser()

format_instructions = PromptTemplate.from_template("""{input}""").partial(
    input=parser.get_format_instructions()
)

dualarm_ppt_ppl = PipelinePromptTemplate(
    final_prompt=full_template_ppt,
    pipeline_prompts=[
        ("template", template_ppt),
        ("task", task_ppt),
        ("system", system_ppt),
        ("domain", domain_ppt),
        ("behaviortree", behaviortree_ppt),
        # ("output_format", output_format_ppt),
        # ("example", example_ppt),
        ("state", state_ppt),
        ("format_instructions", format_instructions),
    ],
)

dualarm_chain = (
    dualarm_ppt_ppl
    # | ChatOpenAI(model="gpt-3.5-turbo-0125", temperature=0)
    # | ChatOpenAI(model="gpt-4o", temperature=0)
    | ChatOpenAI(model="gpt-4o", temperature=0)
    | JsonOutputParser()
)

####################### dual instruction
folder_name = "instruction"
prompt_dir = os.path.join(prompt_dir_base, folder_name)

# * dualarm instruction generation ppl
system_file = os.path.join(prompt_dir, "system.txt")
task_file = os.path.join(prompt_dir, "task.txt")
domain_file = os.path.join(prompt_dir, "domain.txt")
behaviortree_file = os.path.join(prompt_dir, "behaviortree.txt")
# example_file = os.path.join(prompt_dir, "dualarm/example.txt")
# output_format_file = os.path.join(prompt_dir, "dualarm/output_format.txt")
state_file = os.path.join(prompt_dir, "state.txt")
template_file = os.path.join(prompt_dir, "template.txt")
with open(template_file, "r") as f:
    template_ppt = PromptTemplate.from_template(f.read())
with open(task_file, "r") as f:
    task_ppt = PromptTemplate.from_template(f.read())
with open(system_file, "r") as f:
    system_ppt = PromptTemplate.from_template(f.read())
with open(domain_file, "r") as f:
    domain_ppt = PromptTemplate.from_template(f.read())
with open(state_file, "r") as f:
    state_ppt = PromptTemplate.from_template(f.read())
# with open(output_format_file, "r") as f:
    # output_format_ppt = PromptTemplate.from_template(f.read())
with open(behaviortree_file, "r") as f:
    ppt_tmp = PromptTemplate.from_template("{input}")
    behaviortree_ppt = ppt_tmp.partial(input=f.read())
# with open(example_file, "r") as f:
    # ppt_tmp = PromptTemplate.from_template("{input}")
    # example_ppt = ppt_tmp.partial(input=f.read())

full_template_ppt = ChatPromptTemplate.from_template(
    """{system}

    {task}

    {domain}

    {state}

    {behaviortree}

    {template}

    {format_instructions}
    """
)

parser = JsonOutputParser()

format_instructions = PromptTemplate.from_template("""{input}""").partial(
    input=parser.get_format_instructions()
)

instruction_ppt_ppl = PipelinePromptTemplate(
    final_prompt=full_template_ppt,
    pipeline_prompts=[
        ("template", template_ppt),
        ("task", task_ppt),
        ("system", system_ppt),
        ("domain", domain_ppt),
        ("behaviortree", behaviortree_ppt),
        # ("output_format", output_format_ppt),
        # ("example", example_ppt),
        ("state", state_ppt),
        ("format_instructions", format_instructions),
    ],
)

instruction_chain = (
    instruction_ppt_ppl
    | ChatOpenAI(model="gpt-4o", temperature=0)
    | StrOutputParser()
)

####################### mini workflow
mini_workflow_chain = (
    instruction_chain
    | dualarm_ppt_ppl.partial(initial_state=world_state_json) # partial world state to the chain
)


# instruction = """
# The left arm reaches the glass on the table1, grasps it and retreats back.
# The right arm reaches the water bottle on the table2, grasps it and retreats back.
# The right arm then pours the water in the water bottle into the glass. 
# If the glass is not ready, the right arm waits for it.
# After this, the left arm reaches the table1 and release the glass. The right arm reaches the table2 and release the water bottle.
# """

user_input = "please give me a glass of water"

def rollout():
    bt = mini_workflow_chain.invoke(
        {
            "user_input": user_input,
            "world_state": world_state_json,
        }
    )

    print(bt)
    render_bt(bt)

if __name__ == "__main__":
    rollout()
   

