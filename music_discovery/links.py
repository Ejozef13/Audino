from urllib.parse import urlencode


def youtube_search(artist, title):
    """A user-initiated search link, never a claimed verified video match."""
    if not isinstance(artist, str) or not isinstance(title, str) or not artist.strip() or not title.strip():
        return None
    return 'https://www.youtube.com/results?' + urlencode({'search_query': f'{artist} {title} audio'})
