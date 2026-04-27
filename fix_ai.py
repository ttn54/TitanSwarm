import sys

with open('src/core/ai.py', 'r') as f:
    lines = f.readlines()

# Find the insertion point before AITailor class
insertion_point = -1
for i, line in enumerate(lines):
    if line.startswith('class AITailor:'):
        insertion_point = i
        break

if insertion_point != -1:
    new_code = [
        "\ndef _recommended_course_hints(job: Job) -> list[str]:\n",
        "    \"\"\"\n",
        "    Return a list of specific SFU courses or subjects relevant to the job.\n",
        "    \"\"\"\n",
        "    hints = []\n",
        "    role_lower = job.role.lower()\n",
        "    desc_lower = job.job_description.lower()\n",
        "    if \"backend\" in role_lower or \"systems\" in role_lower or \"api\" in desc_lower:\n",
        "        hints.extend([\"CMPT 300: Operating Systems\", \"CMPT 354: Database Systems I\", \"Computer Systems\", \"Data Structures\"])\n",
        "    return hints\n\n"
    ]
    lines[insertion_point:insertion_point] = new_code
    with open('src/core/ai.py', 'w') as f:
        f.writelines(lines)
    print("Successfully patched src/core/ai.py")
else:
    print("Could not find AITailor class")
    sys.exit(1)
