"""
Session context tracking: maintains awareness of the user's current
DaVinci Resolve environment state.
"""

from dataclasses import dataclass, field


@dataclass
class SessionState:
    project_name: str = ""
    project_settings: dict = field(default_factory=dict)
    timeline_name: str = ""
    timeline_track_count: dict = field(default_factory=dict)
    timeline_duration: str = ""
    media_pool_folders: list[str] = field(default_factory=list)
    current_page: str = ""
    render_settings: dict = field(default_factory=dict)
    is_connected: bool = False


class Session:
    """Track the current state of the user's Resolve environment."""

    def __init__(self, resolve_instance=None):
        self.resolve = resolve_instance
        self.state = SessionState()
        if self.resolve:
            self.refresh()

    def refresh(self):
        """Query Resolve API to populate/refresh session state."""
        if not self.resolve:
            self.state.is_connected = False
            return

        try:
            self.state.is_connected = True

            # Current page
            page = self.resolve.GetCurrentPage()
            self.state.current_page = page or ""

            # Project info
            pm = self.resolve.GetProjectManager()
            project = pm.GetCurrentProject()
            if project:
                self.state.project_name = project.GetName() or ""

                # Timeline info
                timeline = project.GetCurrentTimeline()
                if timeline:
                    self.state.timeline_name = timeline.GetName() or ""
                    self.state.timeline_track_count = {
                        "video": timeline.GetTrackCount("video"),
                        "audio": timeline.GetTrackCount("audio"),
                        "subtitle": timeline.GetTrackCount("subtitle"),
                    }
                    start = timeline.GetStartFrame()
                    end = timeline.GetEndFrame()
                    self.state.timeline_duration = f"{end - start} frames"

                # Media pool top-level folders
                media_pool = project.GetMediaPool()
                if media_pool:
                    root = media_pool.GetRootFolder()
                    if root:
                        subfolders = root.GetSubFolderList()
                        self.state.media_pool_folders = [
                            f.GetName() for f in (subfolders or [])
                        ]

                # Render settings (if on Deliver page)
                if self.state.current_page == "deliver":
                    fmt_codec = project.GetCurrentRenderFormatAndCodec()
                    self.state.render_settings = fmt_codec or {}

        except Exception as e:
            self.state.is_connected = False
            self.state = SessionState()
            self.state.is_connected = False

    def get_context_summary(self) -> str:
        """
        Produce a concise text summary of the current Resolve state,
        suitable for injecting into LLM prompts.
        """
        if not self.state.is_connected:
            return (
                "DaVinci Resolve: Not connected. "
                "Running in offline mode — can answer questions but cannot execute scripts."
            )

        parts = [f"DaVinci Resolve: Connected"]

        if self.state.project_name:
            parts.append(f"Project: {self.state.project_name}")

        if self.state.current_page:
            parts.append(f"Current page: {self.state.current_page}")

        if self.state.timeline_name:
            parts.append(f"Active timeline: {self.state.timeline_name}")
            tc = self.state.timeline_track_count
            if tc:
                parts.append(
                    f"  Tracks: {tc.get('video', 0)} video, "
                    f"{tc.get('audio', 0)} audio, "
                    f"{tc.get('subtitle', 0)} subtitle"
                )
            if self.state.timeline_duration:
                parts.append(f"  Duration: {self.state.timeline_duration}")

        if self.state.media_pool_folders:
            parts.append(f"Media pool folders: {', '.join(self.state.media_pool_folders)}")

        if self.state.render_settings:
            parts.append(f"Render settings: {self.state.render_settings}")

        return "\n".join(parts)

    def update_after_action(self, action: str, result) -> None:
        """
        Lightweight state update after executing an action.
        Re-queries only the relevant parts of Resolve state.
        """
        if not self.resolve:
            return

        # For significant state changes, do a full refresh
        state_changing_actions = [
            "CreateProject", "LoadProject", "SetCurrentTimeline",
            "CreateEmptyTimeline", "ImportMedia", "AddTrack",
            "DeleteTrack", "OpenPage",
        ]

        for action_name in state_changing_actions:
            if action_name.lower() in action.lower():
                self.refresh()
                return
