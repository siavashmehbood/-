import time


class BackgroundRunner:
    def __init__(self, scheduler, events):
        self.scheduler = scheduler
        self.events = events
        self.running = False

    def tick(self):
        now = time.strftime('%Y-%m-%dT%H:%M')
        for item in self.scheduler.list(enabled=True):
            if item.get('run_at', '').startswith(now):
                self.events.emit('scheduled_task_due', {'id': item['id'], 'title': item['title']})
                if not item.get('repeat'):
                    self.scheduler.disable(item['id'])

    def run_once(self):
        self.tick()

    def run_forever(self, interval=30):
        self.running = True
        while self.running:
            self.tick()
            time.sleep(interval)

    def stop(self):
        self.running = False
