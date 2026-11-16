# Corpus report

Generated 2026-10-02 by `uv run python -m collector.report` from `data/manifests/documents.jsonl` and `data/manifests/bundles.jsonl`.

Documents: 519. Issuing organizations: 37. Bundles: 191.

## Documents per source

| | count |
|---|---|
| p-portal | 112 |
| hokkaido | 62 |
| koriyama | 49 |
| wakayama_pref | 43 |
| digital | 42 |
| hachioji | 40 |
| asahikawa | 39 |
| okayama_pref | 38 |
| nara_city | 35 |
| funabashi | 29 |
| niigata_pref | 18 |
| jma | 3 |
| kawaguchi | 2 |
| yokosuka | 2 |
| kanazawa | 2 |
| toyama | 1 |
| matsue | 1 |
| kagoshima | 1 |

## Documents per format

| | count |
|---|---|
| pdf | 322 |
| html | 181 |
| zip | 16 |

## Documents per issuing organization

| | count |
|---|---|
| 北海道 | 62 |
| デジタル庁 | 50 |
| 郡山市 | 49 |
| 和歌山県 | 43 |
| 八王子市 | 40 |
| 旭川市 | 39 |
| 岡山県 | 38 |
| 奈良市 | 35 |
| 船橋市 | 29 |
| 新潟県 | 18 |
| 財務省 | 8 |
| 総務省 | 8 |
| 環境省 | 8 |
| 防衛省 | 8 |
| 国土交通省 | 8 |
| 最高裁判所 | 8 |
| 法務省 | 8 |
| 内閣府 | 8 |
| 経済産業省 | 8 |
| 厚生労働省 | 8 |
| 農林水産省 | 7 |
| 個人情報保護委員会 | 4 |
| 気象衛星センター | 3 |
| 文部科学省 | 3 |
| 川口市 | 2 |
| 横須賀市 | 2 |
| 金沢市 | 2 |
| 衆議院 | 2 |
| 人事院 | 2 |
| 消費者庁 | 2 |
| 富山市 | 1 |
| 松江市 | 1 |
| 鹿児島市 | 1 |
| 復興庁 | 1 |
| こども家庭庁 | 1 |
| サイバー通信情報監理委員会 | 1 |
| 公正取引委員会 | 1 |

## Documents per doc_type

| | count |
|---|---|
| notice | 184 |
| other | 66 |
| spec | 59 |
| bid_instructions | 53 |
| tender_page | 35 |
| forms | 31 |
| result | 28 |
| draft_contract | 23 |
| qa | 22 |
| evaluation_criteria | 17 |
| rfi_material | 1 |

## Documents per license_class (D-16)

| | count |
|---|---|
| open | 300 |
| restricted | 167 |
| unknown | 52 |

## IT documents (is_it, D-27)

224 of 503 documents (ZIPs not counted) are IT: システム, クラウド, ソフトウェア, データ or 開発 in the title or the bundle title.

| source | docs | IT docs |
|---|---|---|
| p-portal | 112 | 80 |
| hokkaido | 50 | 4 |
| koriyama | 49 | 25 |
| digital | 42 | 19 |
| wakayama_pref | 42 | 25 |
| hachioji | 40 | 6 |
| asahikawa | 38 | 20 |
| okayama_pref | 36 | 13 |
| nara_city | 35 | 10 |
| funabashi | 29 | 21 |
| niigata_pref | 18 | 0 |
| jma | 3 | 1 |
| kawaguchi | 2 | 0 |
| yokosuka | 2 | 0 |
| kanazawa | 2 | 0 |
| toyama | 1 | 0 |
| matsue | 1 | 0 |
| kagoshima | 1 | 0 |

## Text layer (pdf only)

| | count |
|---|---|
| full | 307 |
| partial | 8 |
| none | 7 |

## Page count (pdf only)

| | count |
|---|---|
| 1-5 | 225 |
| 6-10 | 56 |
| 11-30 | 33 |
| 31-100 | 8 |
| 101-10000 | 0 |

Total pdf pages: 1864.

## Bundles

191 bundles, 47 complete (at least a notice and a spec).

| bundle_id | title | docs | doc types | complete |
|---|---|---|---|---|
| `asahikawa:d078407` | (終了)旭川市地域見守りアプリ開発業務に係る公募型プロポーザルの実施について | 7 | bid_instructions, evaluation_criteria, notice, result, spec 2, tender_page | yes |
| `asahikawa:d079752` | 【公募終了・結果公表】旭川市史デジタルアーカイブ構築業務に係る公募型プロポーザルの実施について | 7 | bid_instructions, evaluation_criteria, notice, qa, result, spec, tender_page | yes |
| `asahikawa:d081809` | 【公募終了・結果公表】旭川市企業情報提供サイト改修等業務公募型プロポーザル実施について | 4 | bid_instructions, notice, result, tender_page |  |
| `asahikawa:d081852` | 【公募終了・結果公表】旭川市災害時緊急情報配信システム整備業務委託に係る公募型プロポーザルの実施について | 7 | bid_instructions, evaluation_criteria, notice, qa, result, spec, tender_page | yes |
| `asahikawa:d082729` | 【公募終了・結果発表】粗大ごみ収集配車管理システム開発業務委託に係る公募型プロポーザルの実施について | 6 | bid_instructions, evaluation_criteria, notice, result, spec, tender_page | yes |
| `asahikawa:d084112` | 旭川市運動部活動地域展開ホームページ作成等業務委託指名型プロポーザルの審査結果について | 5 | bid_instructions, evaluation_criteria, result 2, spec |  |
| `asahikawa:d084856` | 物品購入等に係るオープンカウンターの公示について（案件番号41～42） | 2 | notice, spec | yes |
| `digital:24d6cfea-9b50-4510-9365-64b29f9d5796` | 令和8年度 標準型電子カルテ導入版の設計・開発業務 | 5 | bid_instructions, draft_contract, forms, notice, spec | yes |
| `digital:744a1fec-0699-49a7-aecc-57e18cba2c8a` | 令和8年度ガバメントクラウド利用料に関するダイレクト方式納付の取扱業務 | 6 | bid_instructions 2, notice, other 2, spec | yes |
| `digital:7ce9c12d-a111-4959-80b0-b4a2e4fa61a3` | 令和8年度一般乗用旅客自動車(タクシー)の供給 | 4 | bid_instructions, draft_contract, notice, spec | yes |
| `digital:a6ef7176-6cb9-42fe-bf1a-a70322f49800` | 防災庁のガバメントソリューションサービスへの移行に係るネットワーク環境構築及び保守 | 4 | bid_instructions, draft_contract, notice, spec | yes |
| `digital:c089fc84-8a58-4854-98de-426229726d84` | 地方公共団体の基幹業務システムの統一・標準化におけるデータ要件・連携要件の標準仕様に係る更新作業等の支援業務（令和8年度） | 3 | draft_contract, notice, spec | yes |
| `digital:d06c69d0-3dd0-4758-bed1-f062ba4038c3` | Visit Japan Web利用促進のための協力依頼等に係る業務 | 6 | bid_instructions, draft_contract, forms 2, notice, spec | yes |
| `digital:d08124b1-0d7d-4ecb-8017-1a55aa03f322` | 企業保有情報の新しい提出方法に係るシステム保守等 | 4 | bid_instructions, draft_contract, notice, spec | yes |
| `digital:d0d9097f-4cdd-4524-97a5-0143897922fc` | デジタルPMOの運用・保守業務一式(令和8年度から令和10年度) | 9 | bid_instructions, draft_contract, forms 4, notice, other, spec | yes |
| `funabashi:p143037` | 【受託候補者を特定しました】船橋市消防指令システム設計業務に係るプロポーザルを実施します | 8 | bid_instructions, evaluation_criteria, notice, other 2, qa, result, spec | yes |
| `funabashi:p145678` | 【受託候補者を特定しました】船橋市営住宅管理システム更新業務に関するプロポーザルを実施します | 6 | bid_instructions, evaluation_criteria 2, notice, result, spec | yes |
| `funabashi:p146281` | 【受託候補者を特定しました】船橋市災害情報共有システム導入業務に係る公募型プロポーザルを実施します | 6 | bid_instructions, evaluation_criteria, notice, qa, result, spec | yes |
| `funabashi:p146296` | 【受託候補者を特定しました】アーティストバンクサイト構築及び運用保守業務に係る公募型プロポーザルを実施します | 9 | bid_instructions, evaluation_criteria, notice, other 3, qa, result, spec | yes |
| `hachioji:p025368` | 第2期八王子市国民健康保険データ活用保健事業実施計画の中間評価及び改訂版作成支援業務委託に係る公募型プロポーザルの実施結果について | 6 | bid_instructions 2, qa, result, spec 2 |  |
| `hachioji:p031649` | 【募集は終了しました】公共施設における太陽光発電設備等の設置事業 （自家消費型太陽光発電設備等設置ＰＰＡ事業）の公募型プロポーザル方式による受託者募集 | 6 | bid_instructions 2, notice, other 2, qa |  |
| `hachioji:p032953` | 一般競争入札公告（業務委託、役務、賃貸借、物品の購入・売払い等） | 1 | notice |  |
| `hachioji:p034277` | 【募集は終了しました】市街化調整区域基本方針改定支援業務委託に係る公募型プロポーザル方式による受託者の募集について | 5 | bid_instructions 2, notice, other, qa |  |
| `hachioji:p035062` | 令和7～9年度八王子市特定・一般保健指導（積極的支援）業務委託（単価契約）に係る公募型プロポーザルによる事業者選定の結果について | 4 | bid_instructions, other, result, spec |  |
| `hachioji:p037215` | 生活困窮者自立相談支援事業等業務委託に係る公募型プロポーザルの実施結果について | 4 | bid_instructions, qa, result, spec |  |
| `hachioji:p037225` | 生活保護利用者及び生活困窮者に対する就労支援等業務委託に係る公募型プロポーザルの実施結果について | 4 | bid_instructions, qa, result, spec |  |
| `hachioji:p037290` | 【募集は終了しました】立地適正化計画改定支援業務委託に係る公募型プロポーザル方式による受託者の募集について | 6 | bid_instructions 2, notice, other 2, qa |  |
| `hachioji:p037300` | 夕やけ小やけふれあいの里の段階的リノベーションにおける民間活力導入可能性調査業務委託に係るに係る公募型プロポーザルの実施結果について | 4 | bid_instructions, other, qa, result |  |
| `hokkaido:257922` | 公募型プロポーザルの実施（令和8年度宇宙関連産業振興事業（衛星データ利活用実証事業）委託業務） | 4 | notice, other 2, tender_page |  |
| `hokkaido:267436` | 総合評価一般競争入札の実施　（令和8年度海外販路拡大・投資誘致促進事業） | 6 | evaluation_criteria, notice 2, other 2, tender_page |  |
| `hokkaido:267662` | 一般競争入札の実施（道庁業務RPA環境提供業務）【163-6】 | 8 | draft_contract 2, notice, other 3, spec, tender_page | yes |
| `hokkaido:267870` | 一般競争入札の実施（サケ・マス類養殖に係る種苗生産体制検討委託業務）【157-2】 | 8 | draft_contract, notice 2, other 2, spec 2, tender_page | yes |
| `hokkaido:268275` | 一般競争入札の実施（令和8年度保安林保全情報整備事業（保安林ポリゴン修正）委託業務）【169-7】 | 7 | draft_contract 2, notice, other 2, spec, tender_page | yes |
| `hokkaido:268363` | 一般競争入札の実施（令和８年度（2026 年度）道産木材を活用した庁舎木質化及び普及啓発資料作成委託業務）【171-2】 | 7 | draft_contract, notice 2, other 2, spec, tender_page | yes |
| `hokkaido:268492` | 一般競争入札の実施（デジタル活用人材育成研修業務）【170-5】 | 8 | draft_contract, notice, other 4, spec, tender_page | yes |
| `hokkaido:270635` | 総合評価一般競争入札の実施（令和8年度（2026年度）洋上風力関連産業創出事業委託業務）【187-1】 | 10 | draft_contract, evaluation_criteria 2, notice 2, other 3, spec, tender_page | yes |
| `kagoshima:shiki` | 物品契約入札書・見積書及び委任状 | 1 | other |  |
| `kanazawa:27166` | 制約付き一般競争入札 | 2 | notice 2 |  |
| `kawaguchi:42496` | (物品)オープンカウンター方式対象案件 | 2 | bid_instructions, spec |  |
| `koriyama:107265` | 創業支援ネットワーク推進事業業務委託に係る制限付一般競争入札（令和8年4月13日公告） | 5 | forms 3, notice, tender_page |  |
| `koriyama:126862` | 郡山市図書館情報システム機器類の賃貸借及び保守業務に係る公募型プロポーザルの実施について | 9 | bid_instructions, evaluation_criteria, notice, other 2, result, spec 2, tender_page | yes |
| `koriyama:131705` | 固定資産税データ入力業務に係る制限付一般競争入札（電子入札） | 3 | notice, result, tender_page |  |
| `koriyama:154103` | 郡山市在住外国人との共生ネットワーク構築業務委託に係る公募型プロポーザルの実施について | 8 | bid_instructions, evaluation_criteria, notice, other, qa, result, spec, tender_page | yes |
| `koriyama:183557` | 郡山駅コンパクト・プラス・ネットワーク事業　基本計画策定等業務委託に係る公募型プロポーザルの実施について | 7 | bid_instructions, evaluation_criteria, notice, other, result, spec, tender_page | yes |
| `koriyama:188011` | セーフコミュニティ市民意識調査結果データ作成業務委託に係る制限付一般競争入札について | 7 | notice, other 3, qa, result, tender_page |  |
| `koriyama:194239` | オフィスソフト更新に係るライセンスの追加調達（長期継続契約） | 2 | notice, tender_page |  |
| `koriyama:69957` | 郡山市保健情報管理システムデータ入力業務委託に係る制限付一般競争入札（電子入札）について | 6 | forms 3, notice, other, tender_page |  |
| `koriyama:sample` | 郡山市 公募型プロポーザル (survey sample) | 2 | notice, spec | yes |
| `matsue:16925` | 【物品】入札・見積案件の公開予定 | 1 | other |  |
| `nara_city:268055` | 令和8年度 奈良市DX人材養成事業業務委託　公募型プロポーザルの結果について | 1 | result |  |
| `nara_city:268651` | 校務教育系システム更改に係る情報提供依頼書（RFI）に関する質問への回答を公開します | 2 | qa 2 |  |
| `nara_city:270694` | 介護認定審査会ペーパーレス化システムに係る一般競争入札の結果について | 2 | result 2 |  |
| `nara_city:274696` | 「令和8年度奈良市職員ストレスチェック業務委託」の一般競争入札について | 14 | bid_instructions, draft_contract, forms 9, notice, spec, tender_page | yes |
| `nara_city:275564` | 令和8年度荒廃人工林整備事業業務委託（奈良市Ａ地区）に係る一般競争入札について | 3 | notice, spec, tender_page | yes |
| `nara_city:275565` | 令和8年度荒廃人工林整備事業業務委託（奈良市B地区）に係る一般競争入札について | 3 | notice, spec, tender_page | yes |
| `nara_city:275566` | 令和8年度　鳥獣被害防止施設整備事業　獣害防止柵資材一式の購入に係る一般競争入札 | 4 | notice, other, spec, tender_page | yes |
| `nara_city:2803` | 「休日夜間応急診療所ＰＯＳレジシステム（自動釣銭機連携型）等賃貸借」にかかる一般競争入札を実施します。 | 6 | draft_contract, notice, other 2, spec, tender_page | yes |
| `niigata_pref:20261021touyutankakeiyaku` | 暖房用白灯油共同購入単価契約（一般競争入札、入札日10月21日）柏崎常盤高等学校 | 7 | bid_instructions, draft_contract, forms, notice, other, spec, tender_page | yes |
| `niigata_pref:nyuusatu-r8-kan202` | 気象観測装置の購入（一般競争入札、入札日10月16日）放射線監視センター | 6 | bid_instructions, draft_contract, notice, other, spec, tender_page | yes |
| `niigata_pref:r08tenpikannsouikeitaku12` | 上越工業用水道　天日乾燥池整備及び発生土運搬業務委託 | 5 | draft_contract, notice, other, spec, tender_page | yes |
| `okayama_pref:1047231` | ＲＰＡやＡＩを活用した小規模医療機関の事務省力化に向けた調査業務に関する技術提案結果の公表 | 2 | result 2 |  |
| `okayama_pref:1055020` | 岡山県税コンビニエンスストア収納事務業務の委託に係る一般競争入札(条件付)の公告について | 7 | bid_instructions, forms 2, notice, other, spec, tender_page | yes |
| `okayama_pref:1057597` | 工業技術センター　LANシステム 賃貸借に係る一般競争入札（条件付）の実施について | 6 | bid_instructions, draft_contract, notice, qa, spec, tender_page | yes |
| `okayama_pref:1057598` | 工業技術センター　DTPシステム情報端末 賃貸借に係る一般競争入札（条件付）の実施について | 6 | bid_instructions, draft_contract, notice, qa, spec, tender_page | yes |
| `okayama_pref:1057718` | 岡山県立岡山芳泉高等学校　情報教室教育用電子計算組織 一式借上に係る一般競争入札（条件付）の実施について | 9 | bid_instructions 2, forms 2, notice, other, spec 2, tender_page | yes |
| `okayama_pref:1058412` | 岡山県教育庁高校教育課教育情報化推進室 iPad端末管理ツールライセンス「mobiconnect for education」 １式（1,936ライセンス）調達に係る一般競争入札（条件付）の実施について | 3 | bid_instructions, notice, tender_page |  |
| `okayama_pref:1058476` | 岡山県高度防災情報ネットワーク整備事業被災状況監視システム整備業務に係る一般競争入札（条件付）結果の公表について | 2 | result 2 |  |
| `okayama_pref:1058921` | 岡山県立倉敷南高等学校　情報教室教育用電子計算組織一式借上に係る一般競争入札（条件付）の実施について | 2 | notice, tender_page |  |
| `p-portal:0000000000000241220` | 令和３年度税務大学校における「データ活用研修」の実施委託（区分１） | 1 | notice |  |
| `p-portal:0000000000000289982` | 恩給事務総合システムのデジタル庁所管プラットフォームへの移行要件定義等作成作業の請負 | 1 | notice |  |
| `p-portal:0000000000000305141` | カラー複合機３台の賃貸借及び保守一式 | 1 | notice |  |
| `p-portal:0000000000000331517` | 恩給事務総合システムのガバメントクラウドへの移行に係る作業の請負 | 1 | notice |  |
| `p-portal:0000000000000332713` | 令和４年度瀬戸内海国立公園誘客ツール冊子データ制作業務 | 1 | notice |  |
| `p-portal:0000000000000403270` | 令和５年度大山隠岐国立公園におけるストーリー構築のための観光資源価値調査等業務 | 1 | notice |  |
| `p-portal:0000000000000413944` | 令和５年分確定申告に係る各種パソコンの設定及びインターネット接続環境の構築等並びにパソコン等の備品の借上げ業務 | 1 | notice |  |
| `p-portal:0000000000000420003` | 国債関係システム（国債入札システム）の機能改修に係る設計・開発業務　一式 | 1 | notice |  |
| `p-portal:0000000000000434975` | 須崎第２地方合同庁舎機械設備等保守管理業務 | 1 | notice |  |
| `p-portal:0000000000000440401` | 音響情報処理サブシステムのためのＡＩ維持管理検証基盤の維持管理等支援役務 | 1 | notice |  |
| `p-portal:0000000000000443680` | 高松国税総合庁舎本館外10施設の昇降機設備保守業務（第１グループから第11グループ） | 1 | notice |  |
| `p-portal:0000000000000443684` | 高松国税総合庁舎本館外10施設の昇降機設備保守業務（第１グループから第11グループ） | 1 | notice |  |
| `p-portal:0000000000000443689` | 高松国税総合庁舎本館外10施設の昇降機設備保守業務（第１グループから第11グループ） | 1 | notice |  |
| `p-portal:0000000000000443696` | 高松国税総合庁舎本館外10施設の昇降機設備保守業務（第１グループから第11グループ） | 1 | notice |  |
| `p-portal:0000000000000465863` | 岡山航空気象観測所航空統合気象観測システム通信機器設置等工事 | 1 | notice |  |
| `p-portal:0000000000000491768` | 神戸防災合同庁舎電気・機械設備の日常保守等業務 | 1 | notice |  |
| `p-portal:0000000000000495128` | 神戸防災合同庁舎空調用自動制御機器保守点検業務 | 1 | notice |  |
| `p-portal:0000000000000512482` | 雷監視システム検知局基礎等設置工事設計業務委託 | 1 | notice |  |
| `p-portal:0000000000000520655` | 隠岐航空気象観測所航空統合気象観測システム通信機器設置等工事 | 1 | notice |  |
| `p-portal:0000000000000533540` | 令和７年度「周波数ひっ迫対策技術試験事務」のうち「ドローン用無線局等の高度運用調整技術に関する調査検討のうち、無線局LANに係る自動周波数調整機能の導入に向けた調査検討」の請負 | 1 | notice |  |
| `p-portal:0000000000000536041` | 高松航空気象観測所航空統合気象観測システム通信機器設置等工事 | 1 | notice |  |
| `p-portal:0000000000000536172` | 八尾航空気象観測所航空統合気象観測システム通信機器設置等工事 | 1 | notice |  |
| `p-portal:0000000000000540121` | 関西航空地方気象台 空港気象ドップラーライダー装置定期保守作業 | 1 | notice |  |
| `p-portal:0000000000000541596` | 07-0049-0199 ICTスタートアップの米国ベンチャー・エコシステム連携強化に関する調査の請負 | 1 | notice |  |
| `p-portal:0000000000000547428` | 情報通信・デジタル分野における国際標準化（ルール形成）活動の持続的推進を支える人材基盤の強化に資する講習カリキュラム及び教育プログラム等の整備並びにその実効的運用等に関する調査の~ | 1 | notice |  |
| `p-portal:0000000000000547486` | 07-0049-0230　令和７年度 国際データ取引市場創出事業の請負 | 1 | notice |  |
| `p-portal:0000000000000548725` | 07-0043-0027　電子投票システムのソフトウェア条件及びセキュリティ条件への適合確認にかかる技術検査の請負 | 1 | notice |  |
| `p-portal:0000000000000549103` | Beyond 5Gなどの移動通信システムの社会実装・海外展開を加速するためのビジネス展開志向型の知財・国際標準化戦略に関する調査等の請負 | 1 | notice |  |
| `p-portal:0000000000000562642` | 熊本地裁外冷暖房設備保守点検等業務 | 1 | notice |  |
| `p-portal:0000000000000566531` | 熊本地裁外エレベーター設備保守点検業務 | 1 | notice |  |
| `p-portal:0000000000000576492` | 令和８年度産業廃棄物行政情報システムの機能改善業務 | 1 | notice |  |
| `p-portal:0000000000000600211` | 令和８年度刑事手続のIT化に係る通信サービス用機器等の保守及び運用監視等 | 1 | notice |  |
| `p-portal:0000000000000600516` | 介護サービス情報公表システム機能改修等事業一式 | 1 | notice |  |
| `p-portal:0000000000000601150` | 衆議院立法情報ネットワークシステム及び衆議院インターネット提供情報検索システムの第１期開発業務 | 1 | notice |  |
| `p-portal:0000000000000601871` | 法令・判例等検索システムの利用に係る環境構築及びシステム利用 | 1 | notice |  |
| `p-portal:0000000000000601919` | 法律雑誌等検索システムの利用に係る環境構築及びシステム利用 | 1 | notice |  |
| `p-portal:0000000000000603503` | 第三期監視・監督システムの運用・アプリケーション保守業務 | 1 | notice |  |
| `p-portal:0000000000000604520` | ハローワークシステムの次々期更改に係る調査研究業務及び要件定義書案作成業務等一式 | 1 | notice |  |
| `p-portal:0000000000000606512` | ハローワークシステム国民向けヘルプデスク業務一式 | 1 | notice |  |
| `p-portal:0000000000000606522` | ハローワークシステム統合運用監視・アプリケーションプログラム保守業務(令和９年度運用開始) | 1 | notice |  |
| `p-portal:0000000000000607587` | 国家資格等情報連携・活用システムの利用拡大に伴う機能強化及び性能改善に係る設計・開発業務 | 1 | notice |  |
| `p-portal:0000000000000607695` | 令和8年度～令和9年度 旅費等内部管理業務共通システムの運用業務 | 1 | notice |  |
| `p-portal:0000000000000608647` | 国家公務員経験者の求人・求職者情報サイトの更改に係る設計・開発及び運用・保守業務　一式 | 1 | notice |  |
| `p-portal:0000000000000609775` | 農林水産統計システム次期システム移行・構築に係る調達支援及び技術検討業務 | 1 | notice |  |
| `p-portal:0000000000000612011` | 登記・供託オンライン申請システムの操作サポートデスク業務　一式 | 1 | notice |  |
| `p-portal:0000000000000612605` | 次期府省共通研究開発管理システム（e-Rad）の構築（基本設計） | 1 | notice |  |
| `p-portal:0000000000000612643` | 令和８年度国境離島の合理的・効果的な状況把握手法構築業務 | 1 | notice |  |
| `p-portal:0000000000000612986` | 人口動態調査オンライン報告システム更改に係る調達支援業務一式 | 1 | notice |  |
| `p-portal:0000000000000613931` | 令和７年度岡山刑務所矯正警備システム等更新整備 | 1 | notice |  |
| `p-portal:0000000000000614056` | 【特許庁】共通特実検索（検索部分）・商標検索・審判業務サーバ一式の更改に係るハードウェア等賃貸借及び保守等業務　一式 | 1 | notice |  |
| `p-portal:0000000000000614280` | 地図情報システムの登記所用機器等の賃貸借　一式 | 1 | notice |  |
| `p-portal:0000000000000614304` | 令和８年度産業廃棄物行政情報システムの機能追加業務 | 1 | notice |  |
| `p-portal:0000000000000614317` | 医薬品安定供給・流通確認システムの一部改修に係る設計・開発業務一式 | 1 | notice |  |
| `p-portal:0000000000000614336` | 衆議院立法情報ネットワークシステム及び衆議院インターネット提供情報検索システムの新規開発に係る第１期工程管理等支援業務 | 1 | notice |  |
| `p-portal:0000000000000614777` | 督促手続オンラインシステムの新暗号アルゴリズム対応等改修 | 1 | notice |  |
| `p-portal:0000000000000615359` | 令和８年度岡山刑務所多元放映システム等改修業務 | 1 | notice |  |
| `p-portal:0000000000000615841` | 国内委託教育　デジタル関連（ＡＤＰＳ：アプリケーション開発） | 1 | notice |  |
| `p-portal:0000000000000616356` | 令和８年度高等学校等就学支援金事務処理システムのアプリケーション改修業務　一式 | 1 | notice |  |
| `p-portal:0000000000000616663` | 矯正デジタル化推進計画に基づくコーネットのＧＳＳ移行及び矯正局システム最適化に係る要件定義支援業務の請負　一式 | 1 | notice |  |
| `p-portal:0000000000000616735` | 登記情報提供システムを構成するクラウドサービスの提供等及び機器等の賃貸借　一式 | 1 | notice |  |
| `p-portal:0000000000000616867` | 【資エ庁】令和８年度経済産業省デジタルプラットフォーム構築事業（電気・ガス事業オンライン申請・届出システムに係る機能性向上のための開発（マスタ構築等）） | 1 | notice |  |
| `p-portal:0000000000000616872` | 【資エ庁】令和８年度経済産業省デジタルプラットフォーム構築事業（電気・ガス事業オンライン申請・届出システムに係る機能性向上のための開発（デジタル完結のための共通機能との連携機能搭載 | 1 | notice |  |
| `p-portal:0000000000000617083` | 空調機保守点検 | 1 | notice |  |
| `p-portal:0000000000000617217` | 裁判員制度の運用に関する国民一般の意識等調査業務 | 1 | notice |  |
| `p-portal:0000000000000617362` | 公的個人認証サービスを用いた受付システムの運用・保守、クラウドサービス利用及び改修業務一式（令和９年４月開始） | 1 | notice |  |
| `p-portal:0000000000000617728` | 令和８年度医療従事者届出システムのガバメントクラウド移行に係る調査業務一式 | 1 | notice |  |
| `p-portal:0000000000000617751` | オンライン在留申請処理促進対応に伴う外国人出入国情報システム用端末機器等の供給一式 | 1 | notice |  |
| `p-portal:0000000000000617937` | 令和８年度ガバメントソリューションサービスにおける開発端末の調達 | 1 | notice |  |
| `p-portal:0000000000000618012` | 自治体情報システムに関する情報の取得・管理・活用方法の検討に係る調査検討業務 | 1 | notice |  |
| `p-portal:0000000000000618232` | ＡＩの社会実装によるイノベーションを促進するための情報収集・分析機能構築に係る調査業務 | 1 | notice |  |
| `p-portal:0000000000000618240` | レーザープリンターの賃貸借、保守　一式 | 1 | notice |  |
| `p-portal:0000000000000618279` | 令和８年度　国立研究開発法人によるイノベーションシステム構築に関する調査 | 1 | notice |  |
| `p-portal:0000000000000618539` | 令和８年度特殊土壌地帯推進調査（データ収集・分析・変換等）業務 | 1 | notice |  |
| `p-portal:0000000000000618589` | 市原刑務所及び市原青年矯正センター多元放映システム等更新整備 | 1 | notice |  |
| `p-portal:0000000000000618824` | 民事訴訟手続のデジタル化に係るｅ提出・ｅ記録管理システムに係るヘルプデスク業務 | 1 | notice |  |
| `p-portal:0000000000000618931` | 令和８年度フィードバック収集に基づいたデジタル庁デザインシステムの改善運用に係る調査 | 1 | notice |  |
| `p-portal:0000000000000618997` | 個人データの取扱いに関する責任者に求められるスキル等動向調査 | 1 | notice |  |
| `p-portal:0000000000000619384` | 令和８年度パージ＆トラップGC/MSDシステム一式の購入 | 1 | notice |  |
| `p-portal:0000000000000619502` | 令和８年度刑事手続のIT化に係る通信サービス（専用線サービス）の提供及び保守等（再度公告） | 1 | notice |  |
| `p-portal:0000000000000620533` | 監視設備の保守点検（久里浜地区） | 1 | notice |  |
| `p-portal:0000000000000620612` | 消費者教育推進のための地域ネットワーク構築・強化に関する実証調査 | 1 | notice |  |
| `p-portal:0000000000000621143` | 【本省】令和８年度経済産業省化学物質届出管理業務システムの届出等資料作成支援ツールに係る要件定義支援等業務 | 1 | notice |  |
| `p-portal:0000000000000621175` | 令和８年度人事院システム監査及び情報セキュリティ監査業務 | 1 | notice |  |
| `p-portal:0000000000000621366` | 圧力容器保守点検役務 | 1 | notice |  |
| `p-portal:0000000000000621435` | 【本省】令和８年度技術開発調査等の推進事業（経済産業省調査統計システム現代化（クラウド化・生成AI利活用）事業） | 1 | notice |  |
| `p-portal:0000000000000621786` | 自治体情報システムの運用最適化の実現に向けた複数自治体で連携した知見共有及び運用最適化実施の方法に係る調査検討業務 | 1 | notice |  |
| `p-portal:0000000000000621809` | 令和８年度化学物質環境実態調査データベースシステムに係る調査検討業務 | 1 | notice |  |
| `p-portal:0000000000000622288` | 筆ポリゴンデータ更新業務の効率化に向けたツール導入検討業務 | 1 | notice |  |
| `p-portal:0000000000000622667` | 令和８年度スマート水産業情報システムのうち漁獲情報等伝達サブシステムの調査研究等業務 | 1 | notice |  |
| `p-portal:0000000000000622679` | 令和８年度中小企業実態調査事業（地域における食文化産業エコシステム構築に向けた実証調査事業） | 1 | notice |  |
| `p-portal:0000000000000622735` | 令和８年度食品産業リサイクル状況等調査委託事業（事業者データベース整備及び補完調査等） | 1 | notice |  |
| `p-portal:0000000000000622808` | 浜通り地域等の地域課題解決に向けたローカル・ゼブラ企業のエコシステム形成調査事業 | 1 | notice |  |
| `p-portal:0000000000000622818` | 【防衛装備庁】海洋監視システムの設置作業役務 | 1 | notice |  |
| `p-portal:0000000000000622939` | サイバー通信情報監理委員会の複合機の賃貸借、保守及び消耗品の供給業務 | 1 | notice |  |
| `p-portal:0000000000000623200` | 研究開発支援システムのストレージデータ移行役務（その３） | 1 | notice |  |
| `p-portal:0000000000000623292` | 令和８年度及び令和９年度個人情報保護委員会ウェブサイトシステムの再構築・移行業務 | 1 | notice |  |
| `p-portal:0000000000000623525` | 発電設備保守点検役務 | 1 | notice |  |
| `p-portal:0000000000000623588` | 【本省】令和７年度補正デジタルライフライン整備加速事業（災害対策の高度化に向けた流通関連システムのアーキテクチャ検討に関する調査） | 1 | notice |  |
| `p-portal:0000000000000623622` | 個別換気式飼育ケージシステム（マウス及びラット用）購入 | 1 | notice |  |
| `p-portal:0000000000000623668` | 子ども・子育て支援勘定業務関連システム改修（概算追加交付申請機能構築 ）業務委託 一式 | 1 | notice |  |
| `p-portal:0000000000000623757` | 最高裁判所経理局用度課の事務効率化のためのM365ツールの作成・運用の支援業務 | 1 | notice |  |
| `p-portal:0000000000000623779` | 【資エ庁】令和８年度固定価格買取制度等効率的・安定的運用業務事業（適正な再生可能エネルギーの導入等に関する調査） | 1 | notice |  |
| `p-portal:0000000000000623817` | 令和８年度デジタルフォレンジック用ソフトウェアライセンスの調達（その１９） | 1 | notice |  |
| `p-portal:0000000000000623829` | 次期府省共通研究開発管理システム（e-Rad）の構築（基本設計）における工程管理業務 | 1 | notice |  |
| `p-portal:0000000000000624114` | 日本食品標準成分表の収載値決定等作業のシステム運用・保守業務　一式 | 1 | notice |  |
| `p-portal:0000000000000624170` | 令和８年度 放射性医薬品の開発・製造・利用の促進に関する調査 | 1 | notice |  |
| `p-portal:0000000000000624227` | 【関東森林管理局】峠地すべり試験地観測施設保守点検業務 | 1 | notice |  |
| `p-portal:0000000000000624379` | 消費者庁LINE公式アカウント「消費者庁 若者ナビ！」の運用強化及び利用者参加型情報発信支援業務 | 1 | notice |  |
| `p-portal:0000000000000624446` | 給与関係統計情報処理システムの端末機器の調達及びキッティング業務 | 1 | notice |  |
| `p-portal:0000000000000624655` | 令和８年度から令和12年度犬と猫のマイクロチップ情報登録システムの是正保守等業務 | 1 | notice |  |
| `p-portal:0000000000000624709` | 令和８年度沖縄不発弾等事前調査データベースシステムリプレイス業務 | 1 | notice |  |
| `p-portal:0000000000000624785` | AI開発に用いられる個人情報等の安全管理措置に関する実態調査 | 1 | notice |  |
| `toyama:1017554` | 公募先着による市有財産の売却 | 1 | bid_instructions |  |
| `wakayama_pref:R8_interactive_nyuusatsu` | 令和8年度和歌山県動物愛護センターインタラクティブシステム整備に係る一般競争入札について | 2 | notice, spec | yes |
| `wakayama_pref:d00221579` | 【審査結果を掲載しました】わかやま空き家ポータルサイト構築及び保守管理運営業務委託に係る公募型プロポーザルの実施について | 4 | bid_instructions, notice, qa, spec | yes |
| `wakayama_pref:d00222429` | 令和8年度和歌山県ICT・PHRを活用した特定保健指導基盤整備事業委託業務に係る公募型プロポーザルの実施について | 5 | bid_instructions, draft_contract, notice, qa, spec | yes |
| `wakayama_pref:d00222518` | 【審査結果掲載】和歌山県・市町村被災者生活支援システム構築業務委託に係る公募型プロポーザルの実施について | 5 | bid_instructions, notice, other, qa, spec | yes |
| `wakayama_pref:d00222576` | 【質問への回答掲載】和歌山県職員募集案内2027PR動画制作及び採用試験告知に係るデジタル広報業務に係る公募型プロポーザルの実施について | 8 | bid_instructions, evaluation_criteria, forms, notice, other 2, qa, spec | yes |
| `wakayama_pref:d00222620` | 「きのくに県民カレッジ」・「出張まなび講座」ウェブサイト制作及び講座検索システム 構築業務　　公募型プロポーザル | 6 | bid_instructions, notice, other 2, qa, spec | yes |
| `wakayama_pref:d00222734` | 令和8年度ひだかクラウドファンディング活用推進プロジェクト業務委託プロポーザルに係る公募について | 6 | bid_instructions, forms, notice, other 2, spec | yes |
| `wakayama_pref:d00222761` | 令和8年度和歌山県財務会計システム構築委託・運用保守及び機器等賃貸借に係る一般競争入札の実施について | 2 | bid_instructions, notice |  |
| `wakayama_pref:koubo` | ［審査結果掲載］「令和8年度和歌山県データを利活用した公募型研究事業」に係る公募型プロポーザルの実施について | 4 | bid_instructions, notice, other, spec | yes |
| `yokosuka:kousetupuropo` | 横須賀市公設放課後児童クラブ運営業務委託事業者選定プロポーザル | 2 | bid_instructions, spec |  |

Documents in no bundle (ZIPs excluded): 4. PDFs extracted from ZIPs: 34.

## Documents per org and candidate split

Checks whether an org-level split (D-07, eval_protocol.md) is workable. The split column is a deterministic proposal from `candidate_split` in `collector/report.py` (org counts 60/20/20, largest orgs placed first). The real split is decided in Phase 3. ZIP rows are not counted. Restricted and unknown documents may be used in any split (D-22).

Organizations with 5+ documents: 21 of 37.

| org | license | docs | bundles | candidate split |
|---|---|---|---|---|
| デジタル庁 | open | 50 | 16 | train |
| 北海道 | open | 50 | 8 | train |
| 郡山市 | unknown | 49 | 9 | train |
| 和歌山県 | open | 42 | 9 | train |
| 八王子市 | restricted | 40 | 9 | train |
| 旭川市 | restricted | 38 | 7 | dev |
| 岡山県 | open | 36 | 8 | test |
| 奈良市 | restricted | 35 | 8 | train |
| 船橋市 | restricted | 29 | 4 | test |
| 新潟県 | restricted | 18 | 3 | dev |
| 財務省 | open | 8 | 8 | train |
| 総務省 | open | 8 | 8 | dev |
| 環境省 | open | 8 | 8 | train |
| 防衛省 | open | 8 | 8 | test |
| 国土交通省 | open | 8 | 8 | train |
| 最高裁判所 | open | 8 | 8 | test |
| 法務省 | open | 8 | 8 | dev |
| 内閣府 | open | 8 | 8 | dev |
| 経済産業省 | open | 8 | 8 | test |
| 厚生労働省 | open | 8 | 8 | dev |
| 農林水産省 | open | 7 | 7 | dev |
| 個人情報保護委員会 | open | 4 | 4 | train |
| 気象衛星センター | open | 3 | 0 | test |
| 文部科学省 | open | 3 | 3 | test |
| 川口市 | unknown | 2 | 1 | train |
| 横須賀市 | restricted | 2 | 1 | train |
| 金沢市 | restricted | 2 | 1 | train |
| 衆議院 | open | 2 | 2 | train |
| 人事院 | open | 2 | 2 | train |
| 消費者庁 | open | 2 | 2 | train |
| 富山市 | unknown | 1 | 1 | train |
| 松江市 | restricted | 1 | 1 | train |
| 鹿児島市 | restricted | 1 | 1 | train |
| 復興庁 | open | 1 | 1 | train |
| こども家庭庁 | open | 1 | 1 | train |
| サイバー通信情報監理委員会 | open | 1 | 1 | train |
| 公正取引委員会 | open | 1 | 1 | train |

| split | orgs | orgs with 5+ docs | docs | share of docs | open docs |
|---|---|---|---|---|---|
| train | 23 | 9 | 313 | 62% | 180 |
| dev | 7 | 7 | 95 | 19% | 39 |
| test | 7 | 5 | 95 | 19% | 66 |

Does test rest on at least 4 organizations with 5+ documents? yes: 5 (岡山県 36, 船橋市 29, 最高裁判所 8, 経済産業省 8, 防衛省 8).

## Spot check

Written by hand on 2026-10-02 (Phase 1 exit). `collector.report` keeps this section when it rewrites the report. Ten rows drawn with `random.Random(20261002).sample(rows, 10)` from the 519-row manifest. For each: the file exists at `path` and its SHA-256 equals `doc_id`; for PDFs, PyMuPDF's page count and text-layer check were re-run on the file; for p-portal HTML, the saved page was parsed again (its 調達案件名称 equals `title_ja`, the notice body is present, and 調達種別 agrees with `wto_covered`). doc_type plausibility is my reading of the title, and of page 1 where noted.

| doc_id | source | format | title | doc_type | file + SHA-256 | pages (manifest / file) | text layer (manifest / file) | doc_type plausible? |
|---|---|---|---|---|---|---|---|---|
| `44473a6e7b5e` | okayama_pref | pdf | 1_公告（岡山芳泉） | notice | ok | 3 / 3 | full / full | yes, 公告 = public notice (ZIP member, D-21) |
| `556f1c39ae59` | okayama_pref | pdf | )公告_DTPシステム情報端末 | notice | ok | 2 / 2 | full / full | yes. The stray `)` comes from the ZIP member name |
| `836c1996d0cb` | p-portal | html | 衆議院立法情報ネットワークシステム及び衆議院インターネット提供情報検索システムの新規開発に係る第１期工程管理等支援業務 | notice | ok | - | - | yes. Body 3,706 chars, WTO, English Summary found |
| `0cc5aec9c799` | p-portal | html | 令和８年度中小企業実態調査事業（地域における食文化産業エコシステム構築に向けた実証調査事業） | notice | ok | - | - | yes. Body 8,111 chars, non-WTO, no Summary. Counted as IT only because the title contains 構築 |
| `136dfba9ee59` | p-portal | html | 農林水産統計システム次期システム移行・構築に係る調達支援及び技術検討業務 | notice | ok | - | - | yes. Body 4,175 chars, WTO, English Summary found |
| `d43dd5c2172b` | kanazawa | pdf | 公告文 | notice | ok | 3 / 3 | full / full | yes, 公告文 = notice text |
| `a92bb2644787` | niigata_pref | pdf | 契約書（案） | draft_contract | ok | 2 / 2 | full / full | yes, draft contract |
| `1020085e0999` | asahikawa | pdf | 実施要領別紙（審査項目及び評価基準） | evaluation_criteria | ok | 1 / 1 | full / full | yes, evaluation items and criteria |
| `f695ad396b4c` | koriyama | pdf | 申告調書 | other | ok | 1 / 1 | full / full | **no**: page 1 is a declaration the bidder fills in (circle 該当あり or 該当なし), so `forms`. No cue covers 調書 yet (open question in decisions.md) |
| `70ddd714b85f` | hachioji | pdf | 募集要項 | bid_instructions | ok | 10 / 10 | full / full | yes, 募集要項 = application guidelines |

Result: 10 of 10 files match their hash, page count and text layer. 9 of 10 doc_types are plausible; 1 is too coarse (`other` for a form). No row was edited because of this check. Update at Phase 1 close-out: a 申告調書 -> `forms` cue was added and this row is now `forms`.
