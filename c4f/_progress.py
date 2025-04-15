from collections.abc import Callable, Iterable, Iterator
from enum import Enum, auto
from types import TracebackType
from typing import Any, Dict, List, NamedTuple, Optional, Tuple, Type, TypedDict, Union

from rich.progress import (
    BarColumn,
    DownloadColumn,
    FileSizeColumn,
    MofNCompleteColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TotalFileSizeColumn,
    TransferSpeedColumn,
)

from c4f.utils import console


class ColumnStyling(NamedTuple):
    """Styling for a progress bar column."""

    spinner_style: Optional[str] = None
    bar_width: Optional[int] = None
    complete_style: Optional[str] = None
    pulse_style: Optional[str] = None
    finished_style: Optional[str] = None
    description_style: Optional[str] = None
    percentage_style: Optional[str] = None
    task_progress_style: Optional[str] = None


class ProgressTheme(TypedDict, total=False):
    """Theme for a progress bar."""

    spinner: str
    bar_width: float
    complete_style: str
    finished_style: str
    pulse_style: str
    description_style: str
    percentage_style: str
    task_progress_style: str


class ProgressBarType(Enum):
    """Enum defining different types of progress bars available."""

    DEFAULT = auto()
    SPINNER = auto()
    DOWNLOAD = auto()
    COMMIT = auto()
    INDETERMINATE = auto()
    MINIMAL = auto()
    MULTIPLE = auto()


class ProgressStyler:
    """Class for applying styling to progress bar columns."""

    def style(self, column: ProgressColumn, styling: ColumnStyling) -> ProgressColumn:
        """Apply styling to a single column based on its type.

        Args:
            column (ProgressColumn): The column to style.
            styling (ColumnStyling): Styling options to apply.

        Returns:
            ProgressColumn: The styled column.
        """
        # Map column types to their corresponding styling methods
        styling_methods: Dict[
            Type[Any], Callable[[Any, ColumnStyling], ProgressColumn]
        ] = {
            SpinnerColumn: self._style_spinner_column_if_needed,
            BarColumn: self._style_bar_column_if_needed,
            TextColumn: self._style_text_column_if_needed,
            TaskProgressColumn: self._style_task_progress_column_if_needed,
        }

        # Get the appropriate styling method for the column type
        for column_type, styling_method in styling_methods.items():
            if isinstance(column, column_type):
                return styling_method(column, styling)

        # Return the original column if no styling method is found
        return column

    def _style_spinner_column_if_needed(
        self, column: SpinnerColumn, styling: ColumnStyling
    ) -> ProgressColumn:
        """Apply styling to a spinner column if style is provided.

        Args:
            column (SpinnerColumn): The spinner column to style.
            styling (ColumnStyling): Styling options to apply.

        Returns:
            ProgressColumn: The styled spinner column or original if no styling needed.
        """
        if styling.spinner_style is not None:
            return self._style_spinner_column(styling.spinner_style)
        return column

    def _style_bar_column_if_needed(
        self, column: BarColumn, styling: ColumnStyling
    ) -> ProgressColumn:
        """Apply styling to a bar column if any style is provided.

        Args:
            column (BarColumn): The bar column to style.
            styling (ColumnStyling): Styling options to apply.

        Returns:
            ProgressColumn: The styled bar column or original if no styling needed.
        """
        return self._style_bar_column(
            column,
            styling.bar_width,
            styling.complete_style,
            styling.pulse_style,
            styling.finished_style,
        )

    def _style_text_column_if_needed(
        self, column: TextColumn, styling: ColumnStyling
    ) -> ProgressColumn:
        """Apply styling to a text column based on its content.

        Args:
            column (TextColumn): The text column to style.
            styling (ColumnStyling): Styling options to apply.

        Returns:
            ProgressColumn: The styled text column or original if no styling needed.
        """
        if (
            styling.description_style is not None
            and "[progress.description]" in column.text_format
        ):
            return self._style_description_column(column, styling.description_style)
        if (
            styling.percentage_style is not None
            and "[progress.percentage]" in column.text_format
        ):
            return self._style_text_column(
                column, "progress.percentage", styling.percentage_style
            )
        return column

    def _style_task_progress_column_if_needed(
        self, column: TaskProgressColumn, styling: ColumnStyling
    ) -> ProgressColumn:
        """Apply styling to a task progress column if style is provided.

        Args:
            column (TaskProgressColumn): The task progress column to style.
            styling (ColumnStyling): Styling options to apply.

        Returns:
            ProgressColumn: The styled task progress column or original if no styling needed.
        """
        if styling.task_progress_style is not None:
            return self._style_task_progress_column(styling.task_progress_style)
        return column

    @staticmethod
    def _style_spinner_column(spinner_style: str) -> SpinnerColumn:
        """Style a spinner column with the given style.

        Args:
            spinner_style (str): The spinner style to apply.

        Returns:
            SpinnerColumn: A new styled spinner column.
        """
        # Create a new spinner column with the specified style
        return SpinnerColumn(spinner_name=spinner_style)

    @staticmethod
    def _style_bar_column(
        column: BarColumn,
        bar_width: Optional[int],
        complete_style: Optional[str],
        pulse_style: Optional[str],
        finished_style: Optional[str],
    ) -> BarColumn:
        """Style a bar column with the given styles.

        Args:
            column (BarColumn): The bar column to style.
            bar_width (int, optional): Width for the bar.
            complete_style (str, optional): Style for completed portion.
            pulse_style (str, optional): Style for pulsing animation.
            finished_style (str, optional): Style for finished bar.

        Returns:
            BarColumn: A new styled bar column.
        """
        return BarColumn(
            bar_width=bar_width or column.bar_width,
            complete_style=complete_style or column.complete_style,
            pulse_style=pulse_style or column.pulse_style,
            finished_style=str(finished_style),
        )

    @staticmethod
    def _style_description_column(
        column: TextColumn, description_style: str
    ) -> TextColumn:
        """Style a text column containing a description.

        Args:
            column (TextColumn): The text column to style.
            description_style (str): The style to apply to the description.

        Returns:
            TextColumn: A new styled text column.
        """
        text = column.text_format.replace(
            "[progress.description]", f"[{description_style}]"
        )
        return TextColumn(
            text, justify=column.justify, style=column.style, markup=column.markup
        )

    @staticmethod
    def _style_text_column(column: TextColumn, pattern: str, style: str) -> TextColumn:
        """Style a text column with the given pattern.

        Args:
            column (TextColumn): The text column to style.
            pattern (str): The pattern to replace.
            style (str): The style to apply.

        Returns:
            TextColumn: A new styled text column.
        """
        text = column.text_format.replace(f"[{pattern}]", f"[{style}]")
        return TextColumn(
            text, justify=column.justify, style=column.style, markup=column.markup
        )

    @staticmethod
    def _style_task_progress_column(style: str) -> TaskProgressColumn:
        """Style a task progress column.

        Args:
            style (str): The style to apply.

        Returns:
            TaskProgressColumn: A new styled task progress column.
        """
        return TaskProgressColumn(style=style)


class ProgressBar:
    """Singleton class for creating and managing rich progress bars throughout the application.

    This class provides a centralized way to create and manage progress bars using Rich.
    It supports customizing the appearance and behavior of progress bars, and ensures
    that only one progress bar is active at a time.

    Examples:
        Basic usage:
        ```python
        # Get the progress bar instance
        progress = ProgressBar.get_instance()

        # Create a basic progress bar
        with progress.create() as p:
            task = p.add_task("Processing...", total=100)
            for i in range(100):
                p.update(task, advance=1)
                time.sleep(0.01)
        ```

        Creating a custom progress bar:
        ```python
        progress = ProgressBar.get_instance()
        with progress.create(
            theme="green",
            bar_type=ProgressBarType.DOWNLOAD,
            columns=["spinner", "description", "bar", "percentage", "elapsed"]
        ) as p:
            task = p.add_task("Working...", total=50)
            # ...
        ```

        Using predefined styles:
        ```python
        progress = ProgressBar.get_instance()
        with progress.create(theme="ocean") as p:
            task = p.add_task("Ocean theme progress", total=100)
            # ...
        ```

        Progress tracking with auto-iteration:
        ```python
        progress = ProgressBar.get_instance()
        for item in progress.track(items, description="Processing items"):
            process_item(item)
        ```
    """

    _instance = None

    @classmethod
    def get_instance(cls) -> "ProgressBar":
        """Get the singleton instance of the ProgressBar class.

        Returns:
            ProgressBar: The singleton instance.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        """Initialize the ProgressBar with default settings."""
        if ProgressBar._instance is not None:
            re = "ProgressBar is a singleton! Use get_instance() to get the instance."
            raise RuntimeError(re)

        self.default_columns = [
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ]
        self.default_console = console

        # Define themes for progress bars
        self.themes = self._get_themes()

        # Current active progress bar
        self.active_progress = None

        ProgressBar._instance = self

    @staticmethod
    def _get_themes() -> Dict[str, ProgressTheme]:
        """Get the themes for the progress bars."""
        return {
            "default": {
                "spinner": "dots",
                "bar_width": 40,
                "complete_style": "green",
                "finished_style": "bold green",
                "pulse_style": "blue",
                "percentage_style": "green",
                "task_progress_style": "green",
            },
            "ocean": {
                "spinner": "dots",
                "bar_width": 40,
                "complete_style": "blue",
                "finished_style": "bold cyan",
                "pulse_style": "cyan",
                "percentage_style": "cyan",
                "task_progress_style": "blue",
            },
            "fire": {
                "spinner": "dots",
                "bar_width": 40,
                "complete_style": "red",
                "finished_style": "bold yellow",
                "pulse_style": "yellow",
                "percentage_style": "red",
                "task_progress_style": "red",
            },
            "elegant": {
                "spinner": "line",
                "bar_width": 40,
                "complete_style": "white",
                "finished_style": "bold white",
                "pulse_style": "grey70",
                "percentage_style": "white",
                "task_progress_style": "white",
            },
            "forest": {
                "spinner": "dots",
                "bar_width": 40,
                "complete_style": "green3",
                "finished_style": "bold green",
                "pulse_style": "green_yellow",
                "percentage_style": "green",
                "task_progress_style": "green3",
            },
            "sunset": {
                "spinner": "dots",
                "bar_width": 40,
                "complete_style": "orange3",
                "finished_style": "bold orange1",
                "pulse_style": "red",
                "percentage_style": "orange1",
                "task_progress_style": "orange3",
            },
            "neon": {
                "spinner": "noise",
                "bar_width": 40,
                "complete_style": "hot_pink",
                "finished_style": "bold bright_magenta",
                "pulse_style": "cyan1",
                "percentage_style": "bright_magenta",
                "task_progress_style": "hot_pink",
            },
            "minimal": {
                "spinner": "line",
                "bar_width": 30,
                "complete_style": "white",
                "finished_style": "white",
                "pulse_style": "grey50",
                "percentage_style": "white",
                "task_progress_style": "white",
            },
        }

    def create(
        self,
        description: str = "Working...",
        bar_type: ProgressBarType = ProgressBarType.DEFAULT,
        theme: str = "default",
        columns: Optional[List[Union[str, ProgressColumn]]] = None,
        **kwargs: object,
    ) -> Union[Progress, Tuple[Progress, TaskID]]:
        """Create a customized progress bar based on parameters.

        Args:
            description (str): Description displayed next to the progress bar.
            bar_type (ProgressBarType): Type of progress bar to create.
            theme (str): Theme name from predefined themes.
            columns (List[str|Column]): Column specifications (overrides bar_type's default columns).
            **kwargs: Additional customization options including:
                - spinner_style (str): Style for spinner column.
                - bar_width (int): Width of the progress bar.
                - complete_style (str): Style for completed portion of bar.
                - pulse_style (str): Style for pulsing animation.
                - description_style (str): Style for description text.
                - refresh_per_second (float): Refresh rate.
                - auto_refresh (bool): Whether to auto-refresh.
                - expand (bool): Whether to expand the bar to console width.
                - transient (bool): Whether to remove the progress bar on exit.
                - disable (bool): Whether to disable the progress bar.

        Returns:
            Union[Progress, Tuple[Progress, TaskID]]: For regular progress bars, returns Progress.
            For indeterminate progress bars, returns (Progress, TaskID) tuple.
        """
        # Apply theme settings and prepare kwargs
        kwargs = self._prepare_theme_settings(theme, kwargs)

        # Prepare columns based on bar_type and styling
        styled_columns = self._prepare_columns(bar_type, columns, kwargs)

        # Create and configure progress bar
        progress_bar = self._create_progress_instance(styled_columns, kwargs)

        # Handle indeterminate progress bars
        if bar_type == ProgressBarType.INDETERMINATE:
            task_id = self._setup_indeterminate_progress(progress_bar, description)
            return progress_bar, task_id

        return progress_bar

    def _prepare_theme_settings(
        self, theme: str, kwargs: Dict[str, object]
    ) -> Dict[str, object]:
        """Apply theme settings to kwargs, allowing for overrides.

        Args:
            theme (str): Name of the theme to apply.
            kwargs (dict): Existing kwargs dictionary.

        Returns:
            dict: Updated kwargs with theme settings applied.
        """
        theme_settings = self.themes.get(theme, self.themes["default"])

        # Create a new dict to avoid modifying the original
        updated_kwargs = kwargs.copy()

        # Apply theme settings but allow overrides from kwargs
        for key, value in theme_settings.items():
            if key not in updated_kwargs:
                updated_kwargs[key] = value

        return updated_kwargs

    def _prepare_columns(
        self,
        bar_type: ProgressBarType,
        columns: Optional[List[Union[str, ProgressColumn]]],
        kwargs: Dict[str, object],
    ) -> List[ProgressColumn]:
        """Prepare and style columns for the progress bar.

        Args:
            bar_type (ProgressBarType): Type of progress bar to create.
            columns (List): Column specifications or None.
            kwargs (dict): Kwargs containing styling options.

        Returns:
            List[ProgressColumn]: Styled columns for the progress bar.
        """
        # Setup columns based on bar_type if not explicitly provided
        if columns is None:
            columns = self._get_columns_for_type(bar_type)

        # Process columns specification
        if isinstance(columns, list) and columns and isinstance(columns[0], str):
            columns = self._resolve_column_names(columns)
        elif isinstance(columns, list) and all(
            isinstance(c, ProgressColumn) for c in columns
        ):
            columns = columns
        else:
            # Fallback or raise error for invalid column specification
            columns = self.default_columns

        # Extract styling for columns
        column_styling = self._extract_column_styling(kwargs)

        # Apply column styling
        return self._apply_column_styling(columns, column_styling)

    @staticmethod
    def _extract_column_styling(kwargs: Dict[str, object]) -> ColumnStyling:
        """Extract styling for columns from kwargs."""
        spinner_style = kwargs.get("spinner")
        bar_width = kwargs.get("bar_width")
        complete_style = kwargs.get("complete_style")
        pulse_style = kwargs.get("pulse_style")
        finished_style = kwargs.get("finished_style")
        description_style = kwargs.get("description_style")
        percentage_style = kwargs.get("percentage_style")
        task_progress_style = kwargs.get("task_progress_style")

        return ColumnStyling(
            spinner_style,
            bar_width,
            complete_style,
            pulse_style,
            finished_style,
            description_style,
            percentage_style,
            task_progress_style,
        )

    def _create_progress_instance(
        self, styled_columns: List[ProgressColumn], kwargs: Dict[str, object]
    ) -> Progress:
        """Create a Progress instance with the given columns and settings.

        Args:
            styled_columns (List): Styled columns for the progress bar.
            kwargs (dict): Configuration options for the Progress instance.

        Returns:
            Progress: Configured Progress instance.
        """
        # Set up console
        progress_console = kwargs.pop("console", self.default_console)

        # Create a clean kwargs dict for Progress constructor
        progress_kwargs = {}

        # Copy only the kwargs that are valid for Progress constructor
        valid_progress_kwargs = [
            "refresh_per_second",
            "auto_refresh",
            "expand",
            "transient",
            "disable",
            "get_time",
        ]

        for key in valid_progress_kwargs:
            if key in kwargs:
                progress_kwargs[key] = kwargs[key]

        # Create Progress instance with resolved settings
        progress_bar = Progress(
            *styled_columns, console=progress_console, **progress_kwargs
        )

        # Store as active progress
        self.active_progress = progress_bar

        return progress_bar

    @staticmethod
    def _setup_indeterminate_progress(
        progress_bar: Progress, description: str
    ) -> TaskID:
        """Adds an indeterminate task to the progress bar.

        Args:
            progress_bar (Progress): The progress bar to add the task to.
            description (str): Description of the task.

        Returns:
            TaskID: The ID of the added task.
        """
        task_id: TaskID = progress_bar.add_task(description, total=None)
        return task_id

    def _get_columns_for_type(self, bar_type: ProgressBarType) -> List[ProgressColumn]:
        """Get the appropriate columns for the specified progress bar type.

        Args:
            bar_type (ProgressBarType): The type of progress bar to create.

        Returns:
            List: List of column objects for the specified type.
        """
        column_map = self._get_column_map()

        return column_map.get(bar_type, self.default_columns)

    @staticmethod
    def _get_column_map() -> Dict[ProgressBarType, List[ProgressColumn]]:
        """Get the column map for the progress bar types."""
        return {
            ProgressBarType.SPINNER: [
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
            ],
            ProgressBarType.DOWNLOAD: [
                TextColumn("[bold blue]{task.description}", justify="right"),
                BarColumn(bar_width=None),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
            ],
            ProgressBarType.COMMIT: [
                SpinnerColumn("dots"),
                TextColumn("[bold green]{task.description}"),
                BarColumn(complete_style="green"),
                TaskProgressColumn(),
            ],
            ProgressBarType.MINIMAL: [
                SpinnerColumn("line"),
                TextColumn("[progress.description]{task.description}"),
            ],
            ProgressBarType.MULTIPLE: [
                TextColumn("[bold]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
            ],
        }

    def track(
        self,
        sequence: Iterable[object],
        description: str = "Working...",
        total: Optional[int] = None,
        **kwargs: object,
    ) -> Iterator[object]:
        """Track progress while iterating over a sequence using a default progress bar.

        Args:
            sequence: The sequence to iterate over.
            description (str): Description displayed next to the progress bar.
            total (int, optional): Total number of items if sequence doesn't support len().
            **kwargs: Additional customization options for the progress bar.

        Returns:
            Iterator: An iterator which yields items and updates the progress bar.
        """
        progress = self.create(description=description, **kwargs)

        # Use context manager to ensure proper cleanup
        with progress:
            if total is None:
                try:
                    total = len(sequence)
                except Exception:
                    te = "Cannot determine total length of sequence and `total` was not provided."
                    raise Exception(te) from TypeError
            yield from progress.track(
                sequence, description=description, total=float(total)
            )

    def for_loop(
        self,
        iterable: Iterable[object],
        description: str = "Processing",
        **kwargs: object,
    ) -> "ProgressContext":
        """Context manager for creating a progress bar specifically for a for loop.

        Args:
            iterable: The iterable to loop over.
            description (str): Description for the progress bar.
            **kwargs: Additional customization options.

        Returns:
            ProgressContext: A context manager that yields the progress bar and iterable.
        """
        return ProgressContext(self, iterable, description, **kwargs)

    @staticmethod
    def _resolve_column_names(column_names: List[str]) -> List[ProgressColumn]:
        """Convert column names to actual Rich column objects.

        Args:
            column_names (List[str]): List of column names to resolve.

        Returns:
            List[ProgressColumn]: List of Rich column objects.
        """
        column_map = {
            "spinner": SpinnerColumn(),
            "description": TextColumn("[progress.description]{task.description}"),
            "bar": BarColumn(),
            "percentage": TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            "progress": TaskProgressColumn(),
            "elapsed": TimeElapsedColumn(),
            "remaining": TimeRemainingColumn(),
            "filesize": FileSizeColumn(),
            "totalsize": TotalFileSizeColumn(),
            "download": DownloadColumn(),
            "speed": TransferSpeedColumn(),
            "count": MofNCompleteColumn(),
        }

        resolved_columns = []
        for name in column_names:
            if name in column_map:
                resolved_columns.append(column_map[name])
            else:
                # Default to a text column if name not found
                resolved_columns.append(TextColumn(f"[dim]{name}[/dim]"))

        return resolved_columns

    @staticmethod
    def _apply_column_styling(
        columns: List[ProgressColumn], styling: Optional[ColumnStyling]
    ) -> List[ProgressColumn]:
        """Apply custom styling to columns using ProgressStyler.

        Args:
            columns (List[ProgressColumn]): List of column objects.
            styling (ColumnStyling, optional): Styling options for columns.

        Returns:
            List[ProgressColumn]: List of styled column objects.
        """
        if styling is None:
            return columns
        styler = ProgressStyler()

        return [styler.style(column, styling) for column in columns]

    def get_completion(self, task_id: TaskID) -> float:
        """Get the completion percentage of a task.

        Args:
            task_id: The ID of the task to check.

        Returns:
            float: Completion percentage from 0 to 100.
        """
        if self.active_progress is None:
            return 0.0

        task = self.active_progress.tasks[task_id]
        return task.percentage

    def get_themes(self) -> List[str]:
        """Get a list of available theme names.

        Returns:
            List[str]: List of theme names.
        """
        return list(self.themes.keys())

    def add_theme(self, name: str, theme_settings: ProgressTheme) -> bool:
        """Add a custom theme.

        Args:
            name (str): Name for the theme.
            theme_settings (dict): Theme settings dictionary.

        Returns:
            bool: True if theme was added, False if the name already exists.
        """
        if name in self.themes:
            return False

        self.themes[name] = theme_settings
        return True

    def update_theme(self, name: str, theme_settings: ProgressTheme) -> bool:
        """Update an existing theme.

        Args:
            name (str): Name of the theme to update.
            theme_settings (dict): Theme settings to update.

        Returns:
            bool: True if theme was updated, False if the theme doesn't exist.
        """
        if name not in self.themes:
            return False

        self.themes[name].update(theme_settings)
        return True


class ProgressContext:
    """Context manager specifically designed for tracking progress over an iterable in a for loop."""

    def __init__(
        self,
        progress_bar_manager: ProgressBar,
        iterable: Iterable[object],
        description: str,
        total: Optional[int] = None,
        **kwargs: object,
    ) -> None:
        """Initialize the progress context for a for loop.

        Args:
            progress_bar_manager (ProgressBar): The progress bar singleton.
            iterable: The iterable to track progress for.
            description (str): Description text for the progress bar.
            total (Optional[int]): Total number of items in the iterable. If None, will try to calculate from iterable.
            **kwargs: Additional customization options.
        """
        self.progress_bar = progress_bar_manager
        self.iterable = iterable
        self.description = description
        self.total = total if total is not None else self._get_total(iterable)
        self.kwargs = kwargs
        self.progress = None
        self.task_id = None

    @staticmethod
    def _get_total(iterable: Iterable[object]) -> int:
        """Calculate total items in iterable if possible.

        Args:
            iterable: The iterable to measure.

        Returns:
            int: Total number of items, or 0 if cannot be determined.
        """
        try:
            return len(iterable)
        except (TypeError, AttributeError):
            # If length cannot be determined, return 0 to indicate unknown total
            return 0

    def __enter__(self) -> Tuple[Progress, "ProgressTracker"]:
        """Enter the context manager, creating the progress bar.

        Returns:
            Tuple[Progress, ProgressTracker]: The progress bar and the tracked iterable.
        """
        self.progress = self.progress_bar.create(
            description=self.description, **self.kwargs
        )
        self.task_id = self.progress.add_task(self.description, total=self.total)
        self.progress.start()
        return self.progress, ProgressTracker(
            self.iterable, self.progress, self.task_id
        )

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Exit the context manager, stopping the progress bar."""
        if self.progress:
            self.progress.stop()


class ProgressTracker:
    """Wraps an iterable to automatically update a specific Rich Progress task during iteration."""

    def __init__(
        self, iterable: Iterable[object], progress: Progress, task_id: TaskID
    ) -> None:
        """Initialize the progress tracker.

        Args:
            iterable: The iterable to wrap.
            progress (Progress): The Rich Progress instance.
            task_id: The ID of the task to update.
        """
        self.iterable = iterable
        self.progress = progress
        self.task_id = task_id
        self._iterator: Iterator[object] = iter(iterable)

    def __iter__(self) -> "ProgressTracker":
        """Return self as the iterator."""
        return self

    def __next__(self) -> object:
        """Get the next item from the iterator and advance the associated progress task."""
        item = next(self._iterator)
        self.progress.update(self.task_id, advance=1)
        return item
