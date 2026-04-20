# blog_Backend/blog_Backend/celery.py

import os
from celery import Celery

# 设置 Django 环境，这一步必须在创建 Celery 实例之前
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blog_Backend.settings')

# 创建 Celery 实例，命名为 'blog_Backend'
app = Celery('blog_Backend')

# 从 Django 的 settings 文件中读取 Celery 配置，命名空间为 'CELERY'
# 这样所有 Celery 的配置项都应以 'CELERY_' 开头
app.config_from_object('django.conf:settings', namespace='CELERY')

# 自动发现并注册所有已安装 app 中的 tasks.py 文件
app.autodiscover_tasks()

# 可选：定义一个用于调试的简单任务
@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')