-- INSERT OR REPLACE keeps this file safe to run more than once
INSERT OR REPLACE INTO menu_items (id, name, category, description, price, available) VALUES
 (1,  'Taco de res',       'Tacos',    'Carne de res asada, cebolla, cilantro y salsa', 25, 1),
 (2,  'Taco al pastor',    'Tacos',    'Cerdo al pastor con piña, cebolla y cilantro',  22, 1),
 (3,  'Taco de pollo',     'Tacos',    'Pollo asado con cebolla y salsa',               20, 1),
 (4,  'Taco de birria',    'Tacos',    'Birria de res con consomé',                     30, 0),
 (5,  'Quesadilla',        'Antojitos','Tortilla de harina con queso Oaxaca',           35, 1),
 (6,  'Burrito',           'Antojitos','Tortilla de harina, carne, frijol y queso',     65, 1),
 (7,  'Torta',             'Antojitos','Pan telera con carne, aguacate y frijol',       55, 1),
 (8,  'Guacamole',         'Extras',   'Aguacate, tomate, cebolla y limón',             45, 1),
 (9,  'Orden de frijoles', 'Extras',   'Frijoles charros',                              30, 1),
 (10, 'Agua de horchata',  'Bebidas',  'Vaso de 500 ml',                                25, 1),
 (11, 'Refresco',          'Bebidas',  'Lata de 355 ml',                                20, 1),
 (12, 'Flan',              'Postres',  'Flan napolitano casero',                        35, 1);

-- Closed on Mondays; NULL means closed
INSERT OR REPLACE INTO opening_hours (day_of_week, opens, closes) VALUES
 (1, NULL,    NULL),
 (2, '13:00', '22:00'),
 (3, '13:00', '22:00'),
 (4, '13:00', '22:00'),
 (5, '13:00', '23:30'),
 (6, '13:00', '23:30'),
 (7, '12:00', '20:00');

INSERT OR REPLACE INTO business_info (key, value) VALUES
 ('nombre',     'Taquería El Fogón'),
 ('direccion',  'Av. Ejemplo 123, Col. Centro, Monterrey, N.L.'),
 ('pagos',      'Efectivo, tarjeta y transferencia'),
 ('entrega',    'Servicio a domicilio en un radio de 3 km, costo de envío $30'),
 ('tiempo_entrega', 'Entre 30 y 45 minutos');