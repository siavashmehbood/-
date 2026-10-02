class SecurityPolicy:
    def __init__(self, config, internet_access=None):
        self.internet_access = internet_access
        security = config.get('security', {})
        self.safe_mode = bool(security.get('safe_mode', True))
        improvement = config.get('self_improvement', {})
        self.auto_deploy = bool(improvement.get('auto_deploy', security.get('auto_deploy', False)))
        self.allow_shell = bool(security.get('allow_shell', False))
        self.config_network = bool(security.get('allow_network_tools', False))

    def allows(self, permission, explicit=False):
        if permission == 'read':
            return True
        if permission == 'network':
            if self.internet_access is not None:
                return bool(self.internet_access.status().get('enabled'))
            return bool(self.config_network)
        if permission == 'destructive':
            return bool(explicit) and not self.safe_mode
        if permission == 'input_control':
            return bool(explicit)
        if self.safe_mode and permission in {'write', 'shell', 'deploy'}:
            return False
        if permission == 'shell':
            return self.allow_shell
        if permission == 'deploy':
            return self.auto_deploy
        return True
