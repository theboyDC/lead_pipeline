from bs4 import BeautifulSoup

from src.enrich import _extract_description, _extract_email


def test_extract_description_prefers_meta_description():
    html = '<html><head><meta name="description" content="We build robots."></head><body><p>Other text here that is long enough to be picked up otherwise.</p></body></html>'
    soup = BeautifulSoup(html, "html.parser")
    assert _extract_description(soup) == "We build robots."


def test_extract_description_falls_back_to_first_paragraph():
    html = "<html><body><nav>menu</nav><p>Short</p><p>This is a sufficiently long paragraph describing what the company actually does.</p></body></html>"
    soup = BeautifulSoup(html, "html.parser")
    assert "sufficiently long paragraph" in _extract_description(soup)


def test_extract_email_from_mailto_link():
    html = '<html><body><a href="mailto:hello@example.co.za">Email us</a></body></html>'
    soup = BeautifulSoup(html, "html.parser")
    assert _extract_email(soup, soup.get_text()) == "hello@example.co.za"


def test_extract_email_from_page_text():
    html = "<html><body><p>Contact: hello@example.co.za</p></body></html>"
    soup = BeautifulSoup(html, "html.parser")
    assert _extract_email(soup, soup.get_text(" ")) == "hello@example.co.za"
