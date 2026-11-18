
import pymysql

# Compatibilidad con el backend MySQL de Django
pymysql.version_info = (2, 2, 1, "final", 0)
pymysql.install_as_MySQLdb()
