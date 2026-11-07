# ============================================================================
#  seed.py —— 写入种子商品数据(10-15 个数码 SKU)
#  跑法:python -m app.db.seed   (在 backend/ 下)
# ============================================================================
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine, Base, Product, get_session

# 真实数码配件,字段: 名称/类别/品牌/价格/库存/参数(给 LLM 看的关键 spec)
SEED = [
    # 显卡
    ("RTX 4060 8G",   "显卡", "NVIDIA", 2599, 12, "8GB GDDR6 / 165W / 8K 光追 / 135T 算力"),
    ("RTX 4070 12G",  "显卡", "NVIDIA", 3999, 8,  "12GB GDDR6X / 200W / 4K 电竞 / DLSS3"),
    ("RX 7800 XT",    "显卡", "AMD",    4299, 5,  "16GB GDDR6 / 263W / 4K 高帧 / FSRR"),
    # 显卡补充(覆盖入门/中端/高端/超高端)
    ("RTX 3050 8G",   "显卡", "NVIDIA", 1699, 30, "8GB GDDR6 / 130W / 1080P 入门 / 低功耗"),
    ("RTX 4060 Ti 16G","显卡", "NVIDIA", 3399, 9,  "16GB GDDR6 / 165W / 2K 甜点卡 / 显存大"),
    ("RTX 4080 Super","显卡", "NVIDIA", 8999, 3,  "16GB GDDR6X / 320W / 4K 高刷 / 旗舰性能"),
    ("RTX 4090 24G",  "显卡", "NVIDIA", 13999, 2, "24GB GDDR6X / 450W / 8K / 顶级创作卡"),
    # CPU
    ("i5-14600K",     "CPU",  "Intel",  1899, 20, "14 核 20 线程 / 5.3GHz / LGA1700 / 无核显"),
    ("i7-14700K",     "CPU",  "Intel",  3199, 10, "20 核 28 线程 / 5.6GHz / LGA1700 / 高主频"),
    ("Ryzen 7 9800X3D","CPU",  "AMD",   3699, 6,  "8 核 16 线程 / 5.2GHz / AM5 / 3D V-Cache 游戏强"),
    # 内存
    ("32G DDR5 6000", "内存", "Kingston", 899, 15, "32GB(2x16) / DDR5-6000 / CL36 / 电竞白条"),
    ("64G DDR5 6000", "内存", "G.Skill", 1799, 6,  "64GB(2x32) / DDR5-6000 / RGB 灯条"),
    # 硬盘
    ("1T NVMe SSD",   "硬盘", "Samsung",  799, 30, "1TB / PCIe 4.0 / 读 5000MB/s / M.2 2280"),
    ("2T NVMe SSD",   "硬盘", "WD",       1299, 18, "2TB / PCIe 4.0 / 读 5150MB/s / M.2 2280"),
    # 机箱
    ("全塔机箱 X9",   "机箱", "Cooler Master", 699, 10, "E-ATX / 400mm 显卡 / 12 风扇位"),
    ("ITX 小钢炮",     "机箱", "Fractal",    899, 4,  "Mini-ITX / 短显卡 / 侧透 / 静音"),
    # 电源
    ("850W 金牌",     "电源", "Corsair",  1099, 12, "850W / 80Plus 金牌 / 全模组 / ATX 3.0"),
    ("1000W 金牌",    "电源", "Seasonic",  1599, 5,  "1000W / 80Plus 金牌 / 全模组 / 135mm 风扇"),
    # 散热
    ("240 水冷",      "散热", "Thermalright", 499, 14, "240mm / 兼容 AM5 / 一体式 / 铜底"),
    ("风塔 塔式",     "散热", "Noctua",     799, 8,  "塔式 / 4 热管 / 静音 / AM5 扣具"),
]


def run() -> int:
    Base.metadata.create_all(engine)
    s = get_session()
    # 增量: 按商品名去重, 已存在的跳过, 新补的写入(支持多次跑 seed)
    existing = {p.name for p in s.query(Product.name).all()}
    added = 0
    for n, c, b, p, st, sp in SEED:
        if n in existing:
            continue
        s.add(Product(name=n, category=c, brand=b, price=p, stock=st, spec=sp))
        added += 1
    s.commit()
    s.close()
    if added == 0:
        print(f"[seed] 无新增, 现有 {len(existing)} 个商品")
    else:
        print(f"[seed] 新增 {added} 个, 现有 {len(existing)} -> {len(existing)+added}")
    return 0


if __name__ == "__main__":
    run()
