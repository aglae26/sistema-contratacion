# 1. Imagen base: Usamos un contenedor que ya viene con Node.js instalado (necesario para React)
FROM node:18-alpine

# 2. Definimos la carpeta interna de trabajo
WORKDIR /app

# 3. Copiamos los archivos de configuración de librerías de JavaScript
COPY package.json ./

# 4. Instalamos las dependencias de React
RUN npm install

# 5. Copiamos todo el código de tu aplicación React al contenedor
COPY . .

# 6. Exponemos el puerto 3000 (el puerto por defecto en el que corre React)
EXPOSE 3000

# 7. Comando para arrancar el servidor de desarrollo de React
CMD ["npm", "start"]