
import sys
sys.path.insert(0, '.')

from mcptools.server import MCPServer

def echo(text: str) -> str:
    '''Echo tool - repeats the input text.'''
    return f"Echo: {text}"

def add(a: int, b: int) -> int:
    '''Add tool - adds two numbers.'''
    return a + b

def greet(name: str) -> str:
    '''Greet tool - greets a person by name.'''
    return f"Hello, {name}!"

tools = {
    'echo': echo,
    'add': add,
    'greet': greet,
}

server = MCPServer(port=8004, tools=tools)
server.run()
