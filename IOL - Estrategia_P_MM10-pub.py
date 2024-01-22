# SCRIPT DE TRADING PARA UNA ACCIÓN INDIVIDUAL - API INVERTIR ONLINE ARGENTINA
# Fecha de creación: 09/03/2021
# Desarrollador: Sebastián Matías González

# FUNCIONES A UTILIZAR:
import talib as ta
import openpyxl
import requests
import json
import pandas
import time
from datetime import datetime, timedelta

# ACITVO A TRADEAR:
activo_est="MIRG"

# FUNCIONES PRINCIPALES DEL SCRIPT:
def acceso(usuario="xxxx@mail.com",contraseña="############"):
    return json.loads(requests.post("https://api.invertironline.com/token",data={
        "username":usuario,
        "password":contraseña,
        "grant_type":"password"        
    }).text)["access_token"]

def obtener_info_combinada(activo):
    bearer=acceso()
    url="https://api.invertironline.com/api/v2/bCBA/Titulos/{titulo}/Cotizacion/seriehistorica/{desde}/{hasta}/ajustada?api_key={ber}".format(
        titulo=str(activo),
        desde=(datetime.now() - timedelta(days = 100)).strftime("%Y-%m-%d"),
        hasta=datetime.now().strftime("%Y-%m-%d"),
        ber=str(bearer)
    )
    url2="https://api.invertironline.com/api/v2/{mercado}/Titulos/{simbolo}/Cotizacion".format(
        mercado="bCBA",
        simbolo=activo
    )
    headers = {"Authorization":"Bearer "+str(bearer)}
    serie=json.loads(requests.get(url=url, headers=headers).text)
    ultimo=json.loads(requests.get(url=url2, headers=headers).text)

    return [serie, ultimo]

def refresco(usuario="xxxx@mail.com",contraseña="############"):
    return json.loads(requests.post("https://api.invertironline.com/token",data={
        "username":usuario,
        "password":contraseña,
        "grant_type":"password"        
    }).text)["refresh_token"]

def vender(simbolo, precio, cantidad):
    url = "https://api.invertironline.com/api/v2/operar/Vender"
    headers = {"Authorization":"Bearer "+acceso()}
    data = {
        "mercado": "bCBA",
        "simbolo": simbolo,
        "cantidad": cantidad,
        "precio": precio,
        "validez": datetime.now().strftime("%Y-%m-%d"),
        "plazo":"t0"
    }
    return requests.post(url=url, data=data, headers=headers).text


def comprar(simbolo, precio, cantidad):
    url = "https://api.invertironline.com/api/v2/operar/Comprar"
    headers = {"Authorization":"Bearer "+acceso()}
    data = {
        "mercado": "bCBA",
        "simbolo": simbolo,
        "cantidad": cantidad,
        "precio": precio,
        "validez": datetime.now().strftime("%Y-%m-%d"),
        "plazo":"t0"
    }
    return requests.post(url=url, data=data, headers=headers).text

def disponible():
    url = "https://api.invertironline.com/api/v2/estadocuenta"
    headers = {"Authorization":"Bearer "+acceso()}
    return json.loads(requests.get(url=url, headers=headers).text)["cuentas"][0]["saldos"][0]["disponibleOperar"]

def tenencia_total():
    url = "https://api.invertironline.com/api/v2/estadocuenta"
    headers = {"Authorization":"Bearer "+acceso()}
    return json.loads(requests.get(url=url, headers=headers).text)["totalEnPesos"]

def ordenes_pendientes(activo):
    url = "https://api.invertironline.com/api/v2/operaciones"
    headers = {"Authorization":"Bearer "+acceso()}
    data = {
        "filtro.estado" : "pendientes"
    }
    ordenes=json.loads(requests.get(url=url, headers=headers, data=data).text)

    if len(ordenes)>=1:
        for orden in ordenes:
            if orden["simbolo"] == activo:              
                return [True, orden["numero"]]
            else:
                return [False, 0]
    else:
        return [False, 0]

def borrar_orden(orden):
    url = "https://api.invertironline.com/api/v2/operaciones"
    headers = {"Authorization":"Bearer "+acceso()}
    data = {
        "numero": orden
    }
    return json.loads(requests.delete(url=url, headers=headers, data=data).text)


def activo_en_tenencia(activo):
    url = "https://api.invertironline.com/api/v2/portafolio/argentina"
    headers = {"Authorization":"Bearer "+acceso()}
    
    activos = json.loads(requests.get(url=url, headers=headers).text)["activos"]
    if activos == True:
        for i in activos:
            if i["titulo"]["simbolo"] == activo:
                return [True, json.loads(requests.get(url=url, headers=headers).text)["activos"][i]["cantidad"]]   # si está en tenencia, devuevlo cantidad
            else:
                return [False, 0]
    else:
        return [False, 0]


# UTILIZACIÓN DE FUNCIONES / BLOQUE ITERATIVO:
contador = 0

hora_max = datetime.strptime("17:00:00", "%X").time()
hora_min = datetime.strptime("11:00:00", "%X").time()


while datetime.now().time() <= hora_min:
    print("Aún no abrió el mercado...")
    time.sleep(60)


while True and datetime.now().time() >= hora_min and datetime.now().time() <= hora_max:
    datos = obtener_info_combinada(activo_est)[0]
    ultimo = obtener_info_combinada(activo_est)[1]

    fecha = []
    precio = []
    volumen = []

    for e in datos:
        h = e["fechaHora"][0:10]
        fecha.insert(0, h)
        precio.insert(0, e["ultimoPrecio"])
        volumen.insert(0, e["volumenNominal"])
    
    
    ultima_fecha = ultimo["fechaHora"][0:10]
    if ultima_fecha != fecha[-1]:
        fecha.append(ultima_fecha)
        precio.append(ultimo["ultimoPrecio"])
        volumen.append(ultimo["volumenNominal"])

    preplanilla = {}
    preplanilla["fecha"] = fecha
    preplanilla["precio"] = precio
    preplanilla["volumen"] = volumen
    df = pandas.DataFrame(preplanilla, columns = ["fecha", "precio","volumen"], index=fecha)
    

    df["EMA 10"] = ta.EMA(df["precio"], timeperiod = 10)

    alcista = df["precio"][-1] > df["EMA 10"][-1]
    bajista = df["precio"][-1] < df["EMA 10"][-1]

    liquidez = disponible()

    if ordenes_pendientes(activo_est)[0] == True:                  # Si sigue pendiente a los 300 segundos, cancelamos y mandamos otra
        borrar_orden(ordenes_pendientes(activo_est)[1]) 
        print("ORDEN ANTERIOR CANCELADA")           # accedemos al 2do elemento de la lista que devuelve, que es el nro de orden


    if alcista == True and liquidez > 0 and liquidez > ultimo["ultimoPrecio"]:
        comprar(activo_est, ultimo["ultimoPrecio"], round((liquidez*0.95/ultimo["ultimoPrecio"])))
        print(f"Compraste {activo_est}")

    en_tenencia = activo_en_tenencia(activo_est) 

    if bajista == True and en_tenencia[0] == True and en_tenencia[1] > 0:
        vender(activo_est, ultimo["ultimoPrecio"], en_tenencia[1])
        print(f"Vendiste {activo_est}")

    contador = contador + 1
    print(f"Sistema trabajando... - It. N°: {str(contador)} - {str(datetime.now())}")
    time.sleep(300)




