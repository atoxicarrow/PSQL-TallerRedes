-- Solo se reinicia esta tabla auxiliar, no la tabla equipos.
CREATE TABLE IF NOT EXISTS pruebas_redes (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre TEXT NOT NULL,
    direccion_ip INET NOT NULL
);
TRUNCATE pruebas_redes RESTART IDENTITY;
INSERT INTO pruebas_redes (nombre, direccion_ip)
VALUES ('router', '192.168.1.1'), ('switch', '192.168.1.2');
SELECT * FROM pruebas_redes ORDER BY id;
UPDATE pruebas_redes SET nombre = 'router_actualizado' WHERE id = 1;
SELECT * FROM pruebas_redes ORDER BY id;
DELETE FROM pruebas_redes WHERE id = 2;
SELECT * FROM pruebas_redes ORDER BY id;
