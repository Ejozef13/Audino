"""Display missing measurements distinctly from measured zero."""


def reported_minutes(summary, places=1):
    if summary['duration_events'] == 0:
        return 'Unavailable'
    return f"{summary['reported_duration_ms']/60000:.{places}f}"


def play_events(count):
    return f"{count:,} play {'event' if count == 1 else 'events'}"


def duration_summary(summary, places=1):
    known=summary['duration_events']
    missing=summary['missing_duration_events']
    if known == 0:
        return 'Listening duration unavailable: no imported events report listening time.'
    supplied=f"{known} {'event' if known == 1 else 'events'}"
    absent=f"{missing} {'event lacks' if missing == 1 else 'events lack'} duration"
    return f"Reported listening time: {reported_minutes(summary,places)} minutes from {supplied}; {absent}."


def row_duration(summary):
    if summary['duration_events'] == 0:
        return 'listening time unavailable'
    return reported_minutes(summary)+' reported minutes'
