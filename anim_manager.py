import flet as ft
import asyncio

class AnimationManager:
    def __init__(self):
        self._animations = []
        self._running_tasks = []

    def add_animation(self, control: ft.Control, **kwargs):
        """
        Adds an animation configuration to the manager.
        Args:
            control: The Flet control to animate.
            kwargs: Animation properties like target_scale, target_color, duration, curve, repeat, auto_reverse.
        """
        self._animations.append((control, kwargs))

    async def _animate_control_task(self, control: ft.Control, **kwargs):
        """
        Internal coroutine for animating a single control.
        """
        target_scale = kwargs.get("target_scale")
        target_color = kwargs.get("target_color")
        target_opacity = kwargs.get("target_opacity")
        duration = kwargs.get("duration", 500)
        curve = kwargs.get("curve", ft.AnimationCurve.LINEAR)
        repeat = kwargs.get("repeat", False)
        auto_reverse = kwargs.get("auto_reverse", False)

        # Store initial states to revert to if auto_reverse is true
        initial_scale = control.scale
        initial_color = control.color
        initial_opacity = control.opacity

        try:
            while True:
                # Apply target properties for forward animation
                if target_scale is not None:
                    control.scale = target_scale
                if target_color is not None:
                    control.color = target_color
                if target_opacity is not None:
                    control.opacity = target_opacity
                control.update()

                await asyncio.sleep(duration / 1000)

                if auto_reverse:
                    # Revert to initial properties for reverse animation
                    if target_scale is not None:
                        control.scale = initial_scale
                    if target_color is not None:
                        control.color = initial_color
                    if target_opacity is not None:
                        control.opacity = initial_opacity
                    control.update()

                    await asyncio.sleep(duration / 1000)

                if not repeat:
                    break
        except asyncio.CancelledError:
            # Ensure control reverts to initial state on cancellation
            if target_scale is not None:
                control.scale = initial_scale
            if target_color is not None:
                control.color = initial_color
            if target_opacity is not None:
                control.opacity = initial_opacity
            control.update()

    def start_animation(self, page: ft.Page):
        """
        Starts all registered animations after ensuring controls are attached to the page.
        """
        self.stop_animation()
        self._running_tasks = []

        for control, kwargs in self._animations:
            async def wrapper(ctrl=control, kw=kwargs):
                # Wait until the control is attached to the page (max 5s)
                for _ in range(10):
                    if getattr(ctrl, "_Control__page", None) is not None:
                        break
                    await asyncio.sleep(0.5)
                else:
                    print("⚠️ Controle nunca foi adicionado à página, animação abortada:", ctrl)
                    return

                await self._animate_control_task(ctrl, **kw)

            task = page.run_task(wrapper)
            self._running_tasks.append(task)

        page.update()

    def stop_animation(self):
        """
        Stops all currently running animation tasks.
        """
        for task in self._running_tasks:
            if not task.done():
                task.cancel()
        self._running_tasks = []

    def clear_animations(self):
        """
        Clears all registered animation configurations.
        """
        self.stop_animation()
        self._animations = []
