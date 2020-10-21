FROM arm32v7/python:latest AS build
RUN apt-get update && apt-get install git -y
WORKDIR /app
RUN git clone https://github.com/ToxicGLaDOS/secret-roles.git

FROM arm32v7/python:latest
RUN pip install cherrypy
RUN useradd -ms /bin/bash cherrypy
USER cherrypy
WORKDIR /home/cherrypy/secret-roles
COPY --from=build /app/secret-roles .

ENTRYPOINT ["./main.py"]
