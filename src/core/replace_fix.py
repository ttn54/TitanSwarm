import sys

with open('src/core/ai.py', 'r') as f:
    lines = f.readlines()

# Index 330 in 0-based is line 331 in 1-based
start_idx = 330

new_lines = [
    '        # Code-enforced bullet trim: LLM may ignore the prompt rule, so enforce it here\n',
    '        for i, proj in enumerate(result.tailored_projects):\n',
    '            if i > 0 and proj.keyword_overlap_count <= 2:\n',
    '                proj.bullets = proj.bullets[:2]\n',
    '        return result\n'
]

# We want to replace from line 331 to 335 inclusive
# Lines 331-335 in 0-based are indices 330-334
# Based on my sed output, lines are:
# 331: # Code-enforced...
# 332: for proj ...
# 333: for i, proj ...
# 334:     proj.bullets ...
# 335: return result

# We want to replace indices 330, 331, 332, 333, 334
lines[330:335] = new_lines

with open('src/core/ai.py', 'w') as f:
    f.writelines(lines)
