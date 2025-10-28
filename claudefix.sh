  sudo setenforce 0
  sudo systemctl restart gunicorn
  sudo systemctl restart django-q
  sudo systemctl status gunicorn django-q

