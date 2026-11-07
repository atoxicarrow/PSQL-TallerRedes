CREATE TABLE IF NOT EXISTS equipos (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre TEXT NOT NULL,
    direccion_ip INET NOT NULL
);
INSERT INTO equipos (nombre, direccion_ip)
SELECT 'servidor', '192.168.1.10'::inet
WHERE NOT EXISTS (SELECT 1 FROM equipos WHERE nombre = 'servidor');
INSERT INTO equipos (nombre, direccion_ip)
SELECT 'cliente', '192.168.1.20'::inet
WHERE NOT EXISTS (SELECT 1 FROM equipos WHERE nombre = 'cliente');
SELECT current_database(), current_user, inet_server_addr(), inet_server_port();
SELECT * FROM equipos ORDER BY id;
