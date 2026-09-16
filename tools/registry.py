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
        # Validate the extension point itself. A tool registered with no name or a
        # non-callable handler would only fail later, at call time, far from the code
        # that added it. Extensions are the one place the core cannot see, so they are
        # checked on the way in.
        name = str(getattr(tool, 'name', '') or '').strip()
        if not name:
            raise ValueError('tool must have a non-empty name')
        if not callable(getattr(tool, 'handler', None)):
            raise ValueError(f'tool {name} must have a callable handler')
        if name in self._tools:
            raise ValueError(f'tool already exists: {name}')
        self._tools[name] = tool
        return tool

    def unregister(self, name):
        """Remove a tool. Returns the removed tool, or None if it was not registered.

        Needed so an extension can replace a tool it previously added; without this,
        `register` raising on duplicates left no supported way to change one.
        """
        return self._tools.pop(str(name), None)

    def replace(self, tool):
        """Register a tool, replacing any existing tool with the same name."""
        self.unregister(getattr(tool, 'name', ''))
        return self.register(tool)

    def get(self, name):
        return self._tools.get(name)

    def __contains__(self, name):
        return str(name) in self._tools

    def __len__(self):
        return len(self._tools)

    def names(self):
        return sorted(self._tools)

    def list(self):
        return [{'name': t.name, 'description': t.description, 'safe': t.safe, 'permission': t.permission}
                for t in self._tools.values()]

    def run(self, name, **kwargs):
        tool = self.get(name)
        if not tool:
            raise KeyError(f'unknown tool: {name}')
        return tool.run(**kwargs)
