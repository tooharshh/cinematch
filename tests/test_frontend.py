"""UI behavior tests use a fake Streamlit module, with no network/provider calls."""
import importlib.util
import sys
from unittest.mock import Mock

import pytest
import requests


@pytest.fixture
def frontend(monkeypatch):
    streamlit = Mock()
    monkeypatch.setitem(sys.modules, 'streamlit', streamlit)
    spec = importlib.util.spec_from_file_location('frontend_ui', 'frontend/frontend_app.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, streamlit


def test_timeout_message(frontend, monkeypatch):
    ui, st = frontend
    monkeypatch.setattr(ui.requests, 'request', Mock(side_effect=requests.Timeout))
    assert ui.api_request('GET', '/movies') is None
    assert 'too long' in st.error.call_args.args[0]


@pytest.mark.parametrize('status', [404, 409, 422, 503])
def test_expected_api_errors(frontend, monkeypatch, status):
    ui, st = frontend
    monkeypatch.setattr(ui.requests, 'request', Mock(return_value=Mock(status_code=status)))
    assert ui.api_request('GET', '/movies') is None
    st.warning.assert_called_once()


def test_network_failure(frontend, monkeypatch):
    ui, st = frontend
    monkeypatch.setattr(ui.requests, 'request', Mock(side_effect=requests.ConnectionError))
    assert ui.api_request('GET', '/movies') is None
    st.error.assert_called_once()


def test_success_passes_timeout_and_payload(frontend, monkeypatch):
    ui, _ = frontend
    response = Mock(status_code=200)
    response.json.return_value = {'movies': []}
    transport = Mock(return_value=response)
    monkeypatch.setattr(ui.requests, 'request', transport)
    assert ui.api_request('GET', '/movies', params={'query': 'echo'}) == {'movies': []}
    assert transport.call_args.kwargs['timeout'] == (3, 20)
    assert transport.call_args.kwargs['params'] == {'query': 'echo'}


def test_ui_search_selection_and_metadata_cards(frontend, monkeypatch):
    from unittest.mock import MagicMock
    ui, st = frontend
    st.session_state = {}
    st.form.return_value = MagicMock()
    st.spinner.return_value = MagicMock()
    st.container.return_value = MagicMock()
    st.expander.return_value = MagicMock()
    st.text_input.return_value = 'Inception'
    st.form_submit_button.return_value = True
    st.button.return_value = True
    selected = {'id': 1, 'title': 'Inception', 'year': '2010'}
    st.selectbox.return_value = selected
    result = {'movie': 'inception', 'recommendation_details': [
        {'id': 2, 'title': 'Dream Courier', 'year': '2001', 'genres': 'Thriller',
         'overview': 'A dream heist.', 'rating': 7.0, 'similarity': 0.9}], 'metrics': {}}
    call = Mock(side_effect=[{'movies': [selected]}, result])
    monkeypatch.setattr(ui, 'api_request', call)
    ui.main()
    assert call.call_args.kwargs['json'] == {'movie': 'Inception', 'movie_id': 1, 'num_rec': 5}
    assert any('A dream heist.' in str(call.args[0]) for call in st.markdown.call_args_list)
    assert '1 available alternatives' in st.info.call_args.args[0]


def test_movie_card_escapes_provider_content(frontend):
    ui, _ = frontend
    movie = {'title': '<script>alert(1)</script>', 'overview': '<img src=x onerror=alert(1)>',
             'genres': 'Drama & Mystery', 'year': '2024', 'rating': 7.5, 'similarity': .8}
    card = ui.movie_card(movie, 1)
    assert '<script>' not in card
    assert '<img src=x' not in card
    assert '&lt;script&gt;' in card
    assert 'Drama &amp; Mystery' in card
