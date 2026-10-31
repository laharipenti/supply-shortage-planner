# Reproducibility check

Seed 20261022, scale `starter`. Generated twice into `run_a/` and `run_b/`.

**Reproducible: True** - 54/54 files identical (row count + SHA-256).
Control: seed 20261023 changed 53 files, so the seed really drives the output.

| file | rows | sha256 run A | sha256 run B | match |
|---|---|---|---|---|
| derived/component_requirement.csv | 1579 | c4bdfc87d0556b65... | c4bdfc87d0556b65... | True |
| derived/exception_log.csv | 120 | b15bcca674171c2c... | b15bcca674171c2c... | True |
| derived/inbound_effective.csv | 2312 | a4631ab92ce73a21... | a4631ab92ce73a21... | True |
| derived/mitigation_option.csv | 1011 | d6e4ecd7448f4704... | d6e4ecd7448f4704... | True |
| derived/projected_balance.csv | 29380 | 406f8103a59ad2ff... | 406f8103a59ad2ff... | True |
| derived/shortage.csv | 337 | 8043c18ab6273cae... | 8043c18ab6273cae... | True |
| derived/shortage_event.csv | 1069 | e9178e05883495fd... | e9178e05883495fd... | True |
| derived/supplier_load.csv | 2600 | b97659e0eb8c4f0f... | b97659e0eb8c4f0f... | True |
| ground_truth/ground_truth.csv | 247 | 8a47e6c9ab91c9fb... | 8a47e6c9ab91c9fb... | True |
| ground_truth/ground_truth.json | None | a0a37fbe721ef97e... | a0a37fbe721ef97e... | True |
| input/bom.csv | 55 | 65e79a0523cd699e... | 65e79a0523cd699e... | True |
| input/forecast_demand.csv | 27820 | 0279e249199c4b67... | 0279e249199c4b67... | True |
| input/inventory.csv | 565 | cfa3ebf64760bcfb... | cfa3ebf64760bcfb... | True |
| input/lead_time.csv | 647 | d91482a6d6f8fb5d... | d91482a6d6f8fb5d... | True |
| input/location.csv | 10 | e9847493367abef2... | e9847493367abef2... | True |
| input/po_event.csv | 1236 | 3a8ce725f8e97d10... | 3a8ce725f8e97d10... | True |
| input/production_capacity.csv | 52 | b5dc891694414bae... | b5dc891694414bae... | True |
| input/production_plan.csv | 440 | d5ec866466a5c0d6... | d5ec866466a5c0d6... | True |
| input/purchase_order.csv | 1008 | b703f6f1583863e5... | b703f6f1583863e5... | True |
| input/purchase_order_line.csv | 2312 | bba831213af81c02... | bba831213af81c02... | True |
| input/sku.csv | 300 | 34170c3702ca07c4... | 34170c3702ca07c4... | True |
| input/sku_location.csv | 565 | 6fd154915d929570... | 6fd154915d929570... | True |
| input/sku_substitute.csv | 42 | bcfdcd90d9d6a79d... | bcfdcd90d9d6a79d... | True |
| input/supplier.csv | 50 | 021e50db416e45d5... | 021e50db416e45d5... | True |
| input/supplier_capacity.csv | 2600 | c12761c301029859... | c12761c301029859... | True |
| input/supplier_sku.csv | 518 | 1a6375d44158f7e5... | 1a6375d44158f7e5... | True |
| json/derived/component_requirement.json | None | 71e2ea0feba32e2d... | 71e2ea0feba32e2d... | True |
| json/derived/exception_log.json | None | 4d097a50b8e06f37... | 4d097a50b8e06f37... | True |
| json/derived/inbound_effective.json | None | 0078702c18fa1c8b... | 0078702c18fa1c8b... | True |
| json/derived/mitigation_option.json | None | 57615afaa651515b... | 57615afaa651515b... | True |
| json/derived/projected_balance.json | None | f8ffa43b3db13124... | f8ffa43b3db13124... | True |
| json/derived/shortage.json | None | 55eb4afb355d56a3... | 55eb4afb355d56a3... | True |
| json/derived/shortage_event.json | None | 0248a27885dcd591... | 0248a27885dcd591... | True |
| json/derived/supplier_load.json | None | 3a91bd20c34b4879... | 3a91bd20c34b4879... | True |
| json/ground_truth/ground_truth.json | None | c08fee2944635c13... | c08fee2944635c13... | True |
| json/input/bom.json | None | cfb29fdedfce6740... | cfb29fdedfce6740... | True |
| json/input/forecast_demand.json | None | 64ab1f62f1168dfe... | 64ab1f62f1168dfe... | True |
| json/input/inventory.json | None | 7be653553f2f379b... | 7be653553f2f379b... | True |
| json/input/lead_time.json | None | e5deaba655171509... | e5deaba655171509... | True |
| json/input/location.json | None | c34ed065343e576e... | c34ed065343e576e... | True |
| json/input/po_event.json | None | 2d06312cd306b01c... | 2d06312cd306b01c... | True |
| json/input/production_capacity.json | None | 15de3d3d65ab21df... | 15de3d3d65ab21df... | True |
| json/input/production_plan.json | None | f98c94377b9b1eff... | f98c94377b9b1eff... | True |
| json/input/purchase_order.json | None | 9acf9d5313f02efe... | 9acf9d5313f02efe... | True |
| json/input/purchase_order_line.json | None | e98bc45bb7830271... | e98bc45bb7830271... | True |
| json/input/sku.json | None | 363818e668fd1e4c... | 363818e668fd1e4c... | True |
| json/input/sku_location.json | None | 4d23406ebb0a8796... | 4d23406ebb0a8796... | True |
| json/input/sku_substitute.json | None | 6e31cd35f4206de2... | 6e31cd35f4206de2... | True |
| json/input/supplier.json | None | ce255cda7318838f... | ce255cda7318838f... | True |
| json/input/supplier_capacity.json | None | 7fb4c706403fc5d4... | 7fb4c706403fc5d4... | True |
| json/input/supplier_sku.json | None | 5c8e27527800ba05... | 5c8e27527800ba05... | True |
| sql/ground_truth.sql | None | b7738585fa23d1ca... | b7738585fa23d1ca... | True |
| sql/schema.sql | None | fb3b9a49a6dd1a20... | fb3b9a49a6dd1a20... | True |
| sql/seed.sql | None | 728879e8cd1ac2fe... | 728879e8cd1ac2fe... | True |
