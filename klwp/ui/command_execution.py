"""Apply edit commands and coordinate their UI-side consequences."""


class EditCommandExecutor:
    def __init__(self, owner):
        self._owner = owner

    def execute(self, command):
        result = command.execute()
        if not result["changed"]:
            return result
        self._synchronize_selection(result)
        owner = self._owner
        owner._mark_dirty()
        self._refresh(result)
        self._announce(result)
        return result

    def _synchronize_selection(self, result):
        selection = result["selection"]
        if selection is None:
            return
        owner = self._owner
        owner_type = type(owner)
        selector = getattr(owner_type, "_select_modules", None)
        if selector is not None:
            selector(owner, selection)
            return
        memory = owner.memory
        memory["selected_items"] = tuple(selection)
        memory["selected"] = selection[-1] if selection else None

    def _refresh(self, result):
        owner = self._owner
        if result["refresh"] == "all":
            self._refresh_all(owner, result["selection"])
            return
        owner._render()
        owner._build_props()

    @staticmethod
    def _refresh_all(owner, selection):
        if selection:
            owner._refresh_all(select=selection)
            return
        owner._refresh_all()

    def _announce(self, result):
        status = result["status"]
        if not status:
            return
        owner = self._owner
        owner._set_status(status)


def execute_editor_command(owner, command):
    attributes = vars(owner)
    services = attributes.get("services")
    if services is None:
        from .services import EditorServices
        services = EditorServices(owner)
    return services.execute(command)
