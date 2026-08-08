# Data

Field separator is `;` and decimal mark is `,` in all files. Read with, for example:

```python
pd.read_csv("data/datos_mensual_mediterraneo_revb.csv", sep=";", decimal=",")
```

except `pp_historica_mensual.csv` and `pp_total_anual.csv`, which are standard
comma-separated with a leading index column (`index_col=0`).

## datos_mensual_mediterraneo_revb.csv

One row per basin-month, 2005-2014, 17 basins (two of which the analysis drops).

| Column | Meaning |
|:---|:---|
| `cuenca` | DGA catchment code |
| `year`, `month` | Calendar period |
| `n_transacciones` | Water rights transactions recorded that month |
| `caudal_transado` | Mean flow transacted, litres per second |
| `log_puf_mean` | Log mean transaction price, Unidades de Fomento |
| `pp_max` | Maximum monthly precipitation, mm |
| `qm3_max` | Maximum monthly streamflow, m3/s |
| `dec_esc`, `dummy_escasez` | Water scarcity decrees in force, count and indicator |
| `c_minera`, `dummy_mina` | Mining presence, count and indicator |
| `estival` | Austral summer half-year indicator |
| `lon`, `lat` | Basin centroid, UTM metres |
| `spi` | Superseded drought index, not used; see note below |

The `spi` column is retained only so that earlier drafts can be traced. It was
produced by a routine that fitted a distribution to the year index rather than
to precipitation, and it contains no precipitation information. The analysis
recomputes the index from `pp_historica_mensual.csv`. Do not use this column.

Prices are carried forward in months with no recorded transaction, which is
unavoidable given that a price can only be observed when a trade occurs. 60.4%
of basin-months contain no transaction. See Section 4.2 of the paper for the
sensitivity of the persistence estimate to this.

## pp_historica_mensual.csv

Catchment mean monthly precipitation in mm, 1979-2020, fifteen basins, complete.
Columns: `cuenca`, `year`, `month`, `pp_mes`. This is the input to the drought
index.

## pp_total_anual.csv

The same variable restricted to 2004-2014, named `pp_mean`. Identical to the
overlapping rows of the file above to within 1e-6. Retained for traceability
only, not used by the analysis.

## datos_mensual_mediterraneo_clima_futuro.csv

Rows tagged `escenario` as `base`, `SSP126` or `SSP585`. For the two scenarios,
`pp_max` holds projected *annual* precipitation in mm for 2030, 2050, 2070 and
2090, representing the periods 2021-2040, 2041-2060, 2061-2080 and 2081-2100.
Note that `pp_max` therefore means different things in the base and scenario
rows; the analysis reads only the scenario rows. The `SPI` column is superseded
for the same reason as above and is not used.
