from agent_core.llm import OpenRouterProvider, ToolDefinition

llm = OpenRouterProvider()
tools = [
    ToolDefinition(
        name='list_files',
        description='List all files in a directory',
        parameters={
            'type': 'object',
            'properties': {
                'path': {'type': 'string', 'description': 'Directory path'}
            },
            'required': ['path']
        }
    )
]

r = llm.complete_with_tools(
    'List the files in the current directory',
    tools=tools,
    system_prompt='You have access to tools. Use them when needed.'
)

with open('toolcall_result.txt', 'w') as f:
    f.write('=== Next Tool Call ===\n')
    f.write(f'Finish reason: {r.finish_reason}\n')
    f.write(f'Content: {r.content}\n')
    f.write(f'Number of tool calls: {len(r.tool_calls)}\n')
    
    for i, tc in enumerate(r.tool_calls):
        f.write(f'\nTool Call {i+1}:\n')
        f.write(f'  ID: {tc.id}\n')
        f.write(f'  Name: {tc.name}\n')
        f.write(f'  Arguments: {tc.arguments}\n')

print("Done - results in toolcall_result.txt")
