class HelloEmitter:
    name = "hello-emitter"

    def emit(self, project, dialect="common"):
        return {f"{project.model_name}_hello.txt": f"hello from {project.part_number} using {dialect}\n"}


def register(registry):
    registry.register_emitter(HelloEmitter())
