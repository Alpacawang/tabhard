_registry = {}


class LookupChannel:
    model = None

    def get_query(self, q, request):
        if self.model is None:
            return []
        return self.model.objects.none()

    def format_item_display(self, item):
        return str(item)


def register(name):
    def decorator(cls):
        _registry[name] = cls
        return cls

    return decorator
