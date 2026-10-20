"""Tests for Turkish government bond yields (doviz.com/tahvil)."""

from unittest.mock import Mock

import pytest

from borsapy._providers.dovizcom_tahvil import DovizcomTahvilProvider
from borsapy.cache import Cache
from borsapy.exceptions import DataNotAvailableError

# =============================================================================
# Fixtures
# =============================================================================


def _row(name, slug, flag, last, change):
    return f"""
    <tr data-name="{name}">
      <td>
        <a href="https://www.doviz.com/tahvil/{slug}">
          <img src="https://cdn.doviz.com/images/country_flags/{flag}.png" alt="{name}">
          <div class="currency-details"><div>{name}</div></div>
        </a>
      </td>
      <td class="text-bold">{last}</td>
      <td class="text-bold">%{change}</td>
    </tr>"""


def _page(rows, table_id="bonds"):
    return f"""<html><body>
    <table id="{table_id}">
      <thead><tr><th>Tahvil</th><th>Son</th><th>Değişim</th></tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
    </body></html>"""


# Trimmed from https://www.doviz.com/tahvil (2026-10-20).
BONDS_PAGE = _page(
    [
        _row("TR 2 Yıllık Tahvil Faizi", "tr-2-yillik-tahvil", "tr", "39,58", "0,15"),
        _row("TR 5 Yıllık Tahvil Faizi", "tr-5-yillik-tahvil", "tr", "38,89", "0,39"),
        _row("TR 10 Yıllık Tahvil Faizi", "tr-10-yillik-tahvil", "tr", "35,64", "-0,06"),
        _row("ABD 2 Yıllık Tahvil Faizi", "abd-2-yillik-tahvil", "us", "4,76", "0,04"),
        _row("ABD 10 Yıllık Tahvil Faizi", "abd-10-yillik-tahvil", "us", "5,12", "-0,39"),
        _row("İngiltere 2 Yıllık Tahvil Faizi", "ingiltere-2-yillik-tahvil", "gb", "4,91", "-0,38"),
    ]
)


def _provider(html):
    """Provider with an empty cache whose HTTP GET returns `html`."""
    provider = DovizcomTahvilProvider(cache=Cache())
    provider._get = Mock(return_value=Mock(content=html.encode("utf-8")))
    return provider


# =============================================================================
# Parsing Tests
# =============================================================================


class TestBondYieldsParsing:
    """Tests for DovizcomTahvilProvider.get_bond_yields() against page markup."""

    def test_parses_bonds_table(self):
        """Test the current <table id="bonds"> markup is parsed."""
        bonds = _provider(BONDS_PAGE).get_bond_yields()
        assert [b["maturity"] for b in bonds] == ["2Y", "5Y", "10Y"]

    def test_only_turkish_bonds(self):
        """Test US/UK rows in the same table are excluded."""
        bonds = _provider(BONDS_PAGE).get_bond_yields()
        assert all(b["name"].startswith("TR ") for b in bonds)
        assert 4.76 not in [b["yield"] for b in bonds]

    def test_values(self):
        """Test yield, change and URL are read from the row."""
        ten = _provider(BONDS_PAGE).get_bond("10Y")
        assert ten["yield"] == 35.64
        assert ten["yield_decimal"] == pytest.approx(0.3564)
        assert ten["change_pct"] == -0.06
        assert ten["url"] == "https://www.doviz.com/tahvil/tr-10-yillik-tahvil"

    def test_legacy_commodities_table(self):
        """Test the old <table id="commodities"> id is still accepted."""
        page = _page(
            [_row("TR 10 Yıllık Tahvil Faizi", "tr-10-yillik-tahvil", "tr", "35,64", "0,06")],
            table_id="commodities",
        )
        assert _provider(page).get_bond("10Y")["yield"] == 35.64

    def test_missing_table_raises(self):
        """Test a page without a bond table raises DataNotAvailableError."""
        with pytest.raises(DataNotAvailableError):
            _provider("<html><table id='other'></table></html>").get_bond_yields()

    def test_no_turkish_rows_raises(self):
        """Test a table with only foreign bonds raises DataNotAvailableError."""
        page = _page([_row("ABD 2 Yıllık Tahvil Faizi", "abd-2-yillik-tahvil", "us", "4,76", "0")])
        with pytest.raises(DataNotAvailableError):
            _provider(page).get_bond_yields()

    def test_10y_yield(self):
        """Test get_10y_yield() (used by risk_free_rate()) returns a decimal."""
        assert _provider(BONDS_PAGE).get_10y_yield() == pytest.approx(0.3564)
