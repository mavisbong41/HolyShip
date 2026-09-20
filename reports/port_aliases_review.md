# Port Alias Review

Runtime port aliases are deliberately limited to exact, configurable mappings backed by the
United Nations Code for Trade and Transport Locations (UN/LOCODE). The comparator performs no
fuzzy matching, edit-distance matching, substring matching, or inferred code expansion.

| Canonical port | Alias/code | Rationale/source category | Why safe/general | Used by runtime |
|---|---|---|---|---|
| PORT KLANG | MYPKG | UN/LOCODE: [Malaysia entry](https://service.unece.org/trade/locode/my.htm) | Published location code for Port Klang, independent of participant data | Yes |
| PORT KLANG | MY PKG | UN/LOCODE display form: [Malaysia entry](https://service.unece.org/trade/locode/my.htm) | UN/LOCODE permits the country and location elements to be displayed with a space | Yes |
| SINGAPORE | SGSIN | UN/LOCODE: [Singapore entry](https://service.unece.org/trade/locode/sg.htm) | Published location code for Singapore, independent of participant data | Yes |
| SINGAPORE | SG SIN | UN/LOCODE display form: [Singapore entry](https://service.unece.org/trade/locode/sg.htm) | UN/LOCODE permits the country and location elements to be displayed with a space | Yes |

The canonical names themselves are also exact lookup keys. Similar spellings that are not in the
registry remain unresolved and may proceed to L2; they are never promoted to aliases automatically.
