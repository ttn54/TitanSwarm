        # Code-enforced bullet trim: LLM may ignore the prompt rule, so enforce it here
        for i, proj in enumerate(result.tailored_projects):
            if i > 0 and proj.keyword_overlap_count <= 2:
                proj.bullets = proj.bullets[:2]
        return result
