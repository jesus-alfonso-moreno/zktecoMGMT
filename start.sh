  # 1. Install the django-q2 service
  sudo cp /tmp/django-q.service /etc/systemd/system/django-q.service
  sudo systemctl daemon-reload
  sudo systemctl enable django-q.service
  sudo systemctl start django-q.service

  # 2. Check service status
  sudo systemctl status django-q
  sudo systemctl status gunicorn



  sudo systemctl restart gunicorn
  sudo systemctl restart django-q

