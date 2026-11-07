-- Error intencional: división por cero; no depende de tablas existentes.
SELECT 1 / 0;
-- Se ejecuta en la misma conexión, fuera de una transacción explícita.
SELECT 'conexion_sigue_activa' AS resultado;
