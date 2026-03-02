plugins {
    java
    id("com.google.protobuf") version "0.9.4"
    id("com.github.johnrengelman.shadow") version "8.1.1"
}

group = "bridge"
version = "1.0"

java {
    sourceCompatibility = JavaVersion.VERSION_11
    targetCompatibility = JavaVersion.VERSION_11
}

repositories {
    mavenCentral()
    maven { url = uri("https://repo.runelite.net") }
}

val grpcVersion = "1.62.2"
val protobufVersion = "3.25.3"

dependencies {
    implementation("io.grpc:grpc-netty-shaded:$grpcVersion")
    implementation("io.grpc:grpc-protobuf:$grpcVersion")
    implementation("io.grpc:grpc-stub:$grpcVersion")
    implementation("io.grpc:grpc-services:$grpcVersion")
    implementation("com.google.protobuf:protobuf-java:$protobufVersion")
    implementation("org.slf4j:slf4j-nop:2.0.9")
    compileOnly("org.apache.tomcat:annotations-api:6.0.53")
    compileOnly("net.runelite:client:+")  // Always use latest version
}

protobuf {
    protoc {
        artifact = "com.google.protobuf:protoc:$protobufVersion"
    }
    plugins {
        create("grpc") {
            artifact = "io.grpc:protoc-gen-grpc-java:$grpcVersion"
        }
    }
    generateProtoTasks {
        all().forEach { task ->
            task.plugins {
                create("grpc")
            }
        }
    }
}

sourceSets {
    main {
        proto {
            srcDir("../proto")
        }
    }
}

tasks.shadowJar {
    archiveFileName.set("bridge-server.jar")
    mergeServiceFiles()
    minimize {
        // Netty loads epoll transport via reflection
        exclude(dependency("io.grpc:grpc-netty-shaded:.*"))
    }

    relocate("com.google.protobuf", "bridge.shaded.protobuf")
    relocate("io.grpc", "bridge.shaded.grpc") {
        exclude("io.grpc.netty.shaded.**")  // Keep native library paths intact
    }
    relocate("com.google.common", "bridge.shaded.guava")
    relocate("io.perfmark", "bridge.shaded.perfmark")
    relocate("org.slf4j", "bridge.shaded.slf4j")

    // Strip unnecessary transitive deps
    exclude("com/google/api/**")
    exclude("com/google/cloud/**")
    exclude("com/google/rpc/**")
    exclude("com/google/type/**")
    exclude("com/google/gson/**")
    exclude("org/checkerframework/**")
    exclude("javax/annotation/**")
    exclude("google/**")

    // Linux only - strip non-Linux native libs
    exclude("META-INF/native/*.dll")
    exclude("META-INF/native/*.jnilib")
    exclude("META-INF/native/*_osx_*")
    exclude("META-INF/native/*_windows_*")
    exclude("META-INF/native-image/**/windows-*/**")
    exclude("META-INF/native-image/**/osx-*/**")
}
