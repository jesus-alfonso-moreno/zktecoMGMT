#!/bin/bash
dnf remove postgresql postgresql-server postgresql-contrib
rm -r /var/lib/pgsql
rm -r *env
mkdir /var/lib/pgsql
chown -hR postgres /var/lib/pgsql
