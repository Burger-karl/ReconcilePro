-- Runs once, the first time the postgres volume is created.
-- pytest uses this separate database so tests never touch dev data.
CREATE DATABASE reconcile_test OWNER reconcile;
