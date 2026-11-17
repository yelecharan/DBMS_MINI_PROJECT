-- Run after 05_roles_permissions.sql as a database administrator.
-- Passwords are supplied through psql environment variables, never stored here.
\getenv app_db_password APP_DB_PASSWORD
\getenv worker_db_password WORKER_DB_PASSWORD

SELECT NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'gatesentry_app') AS create_app_role \gset
\if :create_app_role
CREATE ROLE gatesentry_app WITH LOGIN NOINHERIT PASSWORD :'app_db_password';
\endif

SELECT NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'gatesentry_worker') AS create_worker_role \gset
\if :create_worker_role
CREATE ROLE gatesentry_worker WITH LOGIN NOINHERIT PASSWORD :'worker_db_password';
\endif

GRANT gg_admin, gg_security, gg_auditor TO gatesentry_app;
GRANT gg_audit_writer TO gatesentry_app;
GRANT gg_admin TO gatesentry_worker;
GRANT SELECT ON users TO gatesentry_app;
ALTER ROLE gatesentry_worker SET role TO 'gg_admin';
