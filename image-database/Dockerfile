# Modified from https://github.com/NovatecConsulting/opentelemetry-training

FROM --platform=linux/amd64 docker.io/maven:3-eclipse-temurin-21 AS build
WORKDIR /workspace/app

COPY pom.xml .
COPY src src

RUN --mount=type=cache,target=/root/.m2 mvn install -DskipTests
RUN mkdir -p target/dependency && (cd target/dependency; jar -xf ../*.jar)

FROM docker.io/eclipse-temurin:21-jdk-alpine
RUN mkdir -p /opt/imagegenstore
WORKDIR /opt/imagegenstore
#RUN addgroup -S demo && adduser -S demo -G demo
#USER demo
VOLUME /tmp
ARG DEPENDENCY=/workspace/app/target/dependency
COPY --from=build ${DEPENDENCY}/BOOT-INF/lib /opt/imagegenstore/app/lib
COPY --from=build ${DEPENDENCY}/META-INF /opt/imagegenstore/app/META-INF
COPY --from=build ${DEPENDENCY}/BOOT-INF/classes /opt/imagegenstore/app

ADD https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/download/v2.8.0/opentelemetry-javaagent.jar /opt/imagegenstore

ENTRYPOINT ["java", "-cp", "/opt/imagegenstore/app:/opt/imagegenstore/app/lib/*",  "-javaagent:/opt/imagegenstore/opentelemetry-javaagent.jar","dev.tiffanyfay.imagedatabase.ImageDatabaseApplication"]
