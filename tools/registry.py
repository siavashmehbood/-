class Tool:
    def __init__(self, name, description, handler, safe=True, permission=None):
        self.name = name
        self.description = description
        self.handler = handler
        self.safe = safe
        self.permission = permission or ('read' if safe else 'write')

    def run(self, **kwargs):
        return self.handler(**kwargs)

class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, tool):
        if tool.name in self._tools:
            raise ValueError(f'tool already exists: {tool.name}')
        self._tools[tool.name] = tool

    def get(self, name):
        return self._tools.get(name)

    def list(self):
        return [{'name': t.name, 'description': t.description, 'safe': t.safe, 'permission': t.permission}
                for t in self._tools.values()]

    def run(self, name, **kwargs):
        tool = self.get(name)
        if not tool:
            raise KeyError(f'unknown tool: {name}')
        return tool.run(**kwargs)
