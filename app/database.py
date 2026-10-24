import mysql.connector

def get_connection():
    conexion = mysql.connector.connect(
        host="127.0.0.1",
        user="root",
        password="1234",
        database="notvence",
        port=3320
    )

    return conexion