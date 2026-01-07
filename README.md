# arca_dys


<<<<<<< HEAD
Usando AfipSDK (https://app.afipsdk.com/)

Video implementando afipsdk con N8N (https://www.youtube.com/watch?v=A8YK-De1Ikc&t=1652s)

=======

### crear entorno anaconda y posterior hcer el requeriment.txt 

### Docker

### Img tipo adminer SGBD 

### ngrok

-----------------

+ Mientras dejo corriendo tendria que ir modificando la estructura del front o ver como dejarlo mas limpio y sencillo

## Nivel de error en tabla logs_invoice

## No se si funciona el create_log_invoice() en caso de fallo.... Falta un test forzando error

### ver como ordenar las validaciones 



*** ( PREGUNTAS PA EL INGENIERX  )  ***
Cotillon y reposteria lo hardcodie en el bill.html
Pero no lo envias como parametro a la hora generar la factura. Esta bien? 

Faltan datos en la factura me parece:
    cuil
    cond frente al IVA
    apellido y nombre / razon social
    domicilio
    Fecha de vto. para el pago
    ingresos brutos

///
    No se si faltan o no van esos datos 
    No los metas asi nomas en el BILL.HTML.
    Hay q ponerlos en el .env y despues cargarlos en el config.py. Fijate mostri

    Modifique el .env
///

# APP    
ENV=development

# ARCA
ARCA_CUIT='27218282232'
ARCA_PASSWORD="Francisco1109...."
ARCA_ACCESS_TOKEN="8rprObRewp5l6zc0KkFZ13H6sxbwheuKao7rCGN5ZTtOMWCEJ7zhxs3Fce5Z5PVY"
ARCA_ALIAS=afipsdk
ARCA_PTO_VTA=10

# DATABASE
DATABASE_URL=sqlite:///data/app.db
>>>>>>> master
