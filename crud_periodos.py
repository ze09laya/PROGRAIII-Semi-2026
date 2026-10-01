from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from datetime import date, datetime
from math import ceil
from mysql.connector.errors import Error
import conexion


db = conexion.Conexion()


class crud_periodos:

    def _fecha(self, fecha_str):
        """Convierte cadenas 'YYYY-MM-DD' o instancias de date/datetime a un objeto date."""
        if not fecha_str:
            return None
        if isinstance(fecha_str, (date, datetime)):
            return fecha_str if isinstance(fecha_str, date) else fecha_str.date()
        return datetime.strptime(str(fecha_str), '%Y-%m-%d').date()

    def productos(self):
        return db.consultar(
            """
            SELECT idProducto, codigo, nombre
            FROM productos
            WHERE activo = 1
            ORDER BY nombre
            """
        )

    def clientes_empresa(self):
        return db.consultar(
            """
            SELECT idCliente, codigo, nombre
            FROM clientes
            WHERE tipo = 'empresa'
            ORDER BY nombre
            """
        )

    def listar(self, id_cliente):
        return db.consultar(
            """
            SELECT
                p.idPeriodo,
                p.idCliente,
                c.codigo AS codigoCliente,
                c.nombre AS cliente,
                pr.codigo AS codigoProducto,
                pr.nombre AS producto,
                DATE_FORMAT(p.desde, '%Y-%m-%d') AS desde,
                DATE_FORMAT(p.hasta, '%Y-%m-%d') AS hasta,
                p.monto,
                p.cantidad,
                ROUND(p.precio, 2) AS precio,
                ROUND(p.subtotal, 2) AS subtotal,
                p.estado,
                t.desde AS tarifaDesde,
                t.hasta AS tarifaHasta,
                t.precioBase,
                t.adicional,
                t.porcentaje,
                p.versionTarifa,
                p.formula,
                p.fechaCalculo
            FROM periodos_impuesto p
            INNER JOIN clientes c
                ON c.idCliente = p.idCliente
            INNER JOIN productos pr
                ON pr.idProducto = p.idProducto
            INNER JOIN tarifas t
                ON t.idTarifa = p.idTarifa
            WHERE p.idCliente = %s
            ORDER BY p.desde DESC, p.idPeriodo DESC
            """,
            (id_cliente,)
        )

    def calcular(self, datos):
        try:
            if not datos:
                return {'ok': False, 'msg': 'No se recibieron datos.'}

            if not datos.get('idCliente'):
                return {'ok': False, 'msg': 'Debe seleccionar un cliente.'}

            if not datos.get('idProducto'):
                return {'ok': False, 'msg': 'Debe seleccionar un producto.'}

            if not datos.get('desde'):
                return {'ok': False, 'msg': 'Debe indicar la fecha Desde.'}

            if not datos.get('hasta'):
                return {'ok': False, 'msg': 'Debe indicar la fecha Hasta.'}

            if datos.get('monto') is None or str(datos.get('monto')).strip() == '':
                return {'ok': False, 'msg': 'Debe ingresar el balance.'}

            id_cliente_recibido = str(datos.get('idCliente')).strip()
            id_producto = int(datos.get('idProducto'))

            fecha_desde = self._fecha(datos.get('desde'))
            fecha_hasta = self._fecha(datos.get('hasta'))

            monto = Decimal(str(datos.get('monto')))

            if fecha_desde >= fecha_hasta:
                return {'ok': False, 'msg': 'La fecha Hasta debe ser posterior a la fecha Desde.'}

            if monto <= 0:
                return {'ok': False, 'msg': 'Ingrese un balance mayor que cero.'}

            cliente = db.consultar(
                """
                SELECT idCliente, codigo, nombre, tipo
                FROM clientes
                WHERE CAST(idCliente AS CHAR) = %s
                   OR codigo = %s
                   OR CAST(codigo AS UNSIGNED) = CAST(%s AS UNSIGNED)
                LIMIT 1
                """,
                (id_cliente_recibido, id_cliente_recibido, id_cliente_recibido)
            )

            if not cliente:
                return {'ok': False, 'msg': f'El cliente no existe. Valor recibido: {id_cliente_recibido}'}

            cliente_data = cliente[0] if isinstance(cliente, list) else cliente

            if cliente_data.get('tipo') != 'empresa':
                return {'ok': False, 'msg': 'El Impuesto a las Actividades Económicas requiere un cliente de tipo empresa.'}

            producto = db.consultar(
                """
                SELECT idProducto, codigo, nombre
                FROM productos
                WHERE idProducto = %s AND activo = 1
                """,
                (id_producto,)
            )

            if not producto:
                return {'ok': False, 'msg': 'El producto no existe o está inactivo.'}

            producto_data = producto[0] if isinstance(producto, list) else producto

            tarifas = db.consultar(
                """
                SELECT *
                FROM tarifas
                WHERE idProducto = %s
                  AND activo = 1
                  AND fechaDesde <= %s
                  AND (fechaHasta IS NULL OR %s < fechaHasta)
                  AND desde <= %s
                  AND hasta >= %s
                ORDER BY idTarifa
                """,
                (id_producto, fecha_desde, fecha_desde, monto, monto)
            )

            if not tarifas or len(tarifas) == 0:
                return {'ok': False, 'msg': 'No existe una tarifa configurada para el balance indicado.'}

            if len(tarifas) > 1:
                return {'ok': False, 'msg': 'Existe más de una tarifa aplicable. Corrija la tabla tarifaria.'}

            tarifa = tarifas[0]

            precio_base = Decimal(str(tarifa.get('precioBase') or 0))
            adicional = Decimal(str(tarifa.get('adicional') or 0))
            porcentaje = Decimal(str(tarifa.get('porcentaje') or 0))
            desde_tarifa = Decimal(str(tarifa.get('desde') or 0))

            if porcentaje > 0:
                precio = (monto * porcentaje) / Decimal('100')
                excedente = monto - desde_tarifa
                bloques = Decimal('0')
                formula = (
                    f"Impuesto mensual = {monto:.2f} x {porcentaje:.4f}% / 100 = "
                    f"{precio.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"
                )
            else:
                excedente = monto - desde_tarifa
                if excedente <= 0:
                    bloques_int = 0
                else:
                    bloques_int = ceil(float(excedente / Decimal('1000')))

                bloques = Decimal(str(bloques_int))
                precio = precio_base + (bloques * adicional)

                formula = (
                    f"Excedente = {monto:.2f} - {desde_tarifa:.2f} = {excedente:.2f}; "
                    f"Bloques = CEIL({excedente:.2f} / 1,000) = {bloques_int}; "
                    f"Impuesto mensual = {precio_base:.2f} + ({bloques_int} x {adicional:.2f}) = "
                    f"{precio.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"
                )

            precio = precio.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
            subtotal = precio

            version_tarifa = str(tarifa.get('version') or '1.0')

            return {
                'ok': True,
                'cliente': cliente_data.get('nombre', ''),
                'producto': producto_data.get('nombre', ''),
                'tarifa': {
                    'idTarifa': tarifa.get('idTarifa'),
                    'desde': str(tarifa.get('desde', 0)),
                    'hasta': str(tarifa.get('hasta', 0)),
                    'precioBase': str(precio_base),
                    'adicional': str(adicional),
                    'porcentaje': str(porcentaje),
                    'version': version_tarifa
                },
                'monto': str(monto),
                'excedente': str(excedente),
                'bloques': str(bloques),
                'precio': str(precio),
                'subtotal': str(subtotal),
                'formula': formula
            }

        except Exception as e:
            print(f"--- ERROR INTERNO EN CALCULAR ---: {type(e).__name__} - {e}")
            return {'ok': False, 'msg': f'Error en procesamiento: {type(e).__name__} - {e}'}

    def administrar(self, datos):
        conn = db.conectar()

        if not conn:
            return 'Error de conexión a la base de datos'

        try:
            accion = datos.get('accion', 'nuevo')

            if accion != 'nuevo':
                return 'Los períodos históricos no se modifican automáticamente.'

            calculo = self.calcular(datos)

            if not calculo.get('ok'):
                return calculo.get('msg', 'Error al realizar el cálculo')

            tarifa_info = calculo.get('tarifa', {})
            version_tarifa = tarifa_info.get('version', '1.0')

            sql = """
                INSERT INTO periodos_impuesto
                (idCliente, idProducto, idTarifa, desde, hasta, monto, cantidad, precio, subtotal, estado, versionTarifa, formula, fechaCalculo)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """

            valores = (
                datos.get('idCliente'),
                datos.get('idProducto'),
                tarifa_info.get('idTarifa'),
                datos.get('desde'),
                datos.get('hasta'),
                calculo.get('monto'),
                1,
                calculo.get('precio'),
                calculo.get('subtotal'),
                'registrado',
                version_tarifa,
                calculo.get('formula')
            )

            return db.ejecutar(sql, valores)

        except Error as e:
            return f'Error al registrar el período: {e}'
        except Exception as e:
            return f'Error inesperado en administrar: {e}'