from agent_core.agent import create_agent

agent = create_agent(verbose=False)
result = agent.run('What is 2 + 2? Answer with just the number.')
with open('final_response.txt', 'w') as f:
    f.write('=== Final Response ===\n')
    f.write(repr(result))
print("Done")
