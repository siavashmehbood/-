from pathlib import Path
import shutil


def check_system(root, brain):
    disk = shutil.disk_usage(Path(root).anchor)
    return {
        'project': str(root),
        'disk_free_gb': round(disk.free / 1024**3, 2),
        'model': brain.health(),
    }
