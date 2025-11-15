#!/bin/bash
# اسکریپت برای اجرای تست دریافت Node از Core

docker exec deployment-web-1 python manage.py shell -c "
from ingest.tests.test_core_node_fetch import test_fetch_sample_node
test_fetch_sample_node()
"
