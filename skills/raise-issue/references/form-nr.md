# Form — NR (new requirement)

Ops muốn một thứ **chưa tồn tại**. Nếu thứ đó đã tồn tại nhưng chạy sai → `form-bug.md`. Nếu đã tồn tại và chạy đúng-như-thiết-kế nhưng cần đổi hành vi → `form-cr.md`.

**Slot bắt buộc (mẫu số của `completeness`) = 9**: §1 · §2 · §3 · §7 · §8 · §9 · user story · giá trị nghiệp vụ · **integration point**.

`integration point` **bắt buộc** vì tính năng mới không bao giờ tồn tại độc lập trong một codebase đã có. Không biết nó gắn vào đâu thì phase analyze không có điểm xuất phát và sẽ thiết kế một thứ rời rạc.

Không xoá section nào. Rỗng thì in nhãn. Thứ tự cố định.

---

## Khung rỗng — copy y hệt

```markdown
---
id: <slug>
raised_at: <ISO 8601 local>
type: NR
title: <một câu, ≤ 100 ký tự>
area: <cách repo này gọi vùng đó>
reported_severity: <nguyên lời ops>
gh_issue: <N>
sources: [ops-chat]
confirmed_by_ops: true
supersedes: <file raise trước>
completeness: <n>/9
next: analyze
---

# NR: <title>

## §1. Vấn đề trong một câu

<một câu duy nhất: thiếu cái gì>

## §2. Hiện trạng — khoảng trống hôm nay

- **Hiện ops/user đang phải làm gì thay thế**: <workaround thủ công, nếu có>
- **Cái gì hiện KHÔNG có**: <…>
- **Đã từng tồn tại chưa**: không (nếu "có" → sai form, đây là BUG hoặc CR)

## §3. Kỳ vọng — mong muốn

- **User story**: Là <loại user>, tôi muốn <hành động>, để <giá trị nhận được>. — <bắt buộc>
- **Giá trị nghiệp vụ / pain point**: <bắt buộc — vì sao đáng làm>
- **Tiêu chí quan sát được** (nếu ops đã nêu):
  - [ ] <hành vi quan sát được 1>

## §4. Bằng chứng (nếu có)

- **Ai yêu cầu / từ đâu**: <ops / PM / khách / issue>
- **Ảnh**: `[SCREENSHOT]` <mô tả chữ những gì đọc được trong ảnh + nguồn>

## §5. Vùng code liên quan — integration point

| Gắn vào đâu | Kết quả | Nhãn |
|---|---|---|
| <màn / luồng / component ops nêu> | <path:line hoặc "không tìm thấy"> | `[VERIFIED]` / `[UNVERIFIED]` / `[LOCATED … ← anchor "<s>" trong <vùng>]` |

- **Vào UI tại**: <bắt buộc — màn nào, chỗ nào trên màn>
- **Đọc/ghi dữ liệu nào** (nếu ops nêu): <…>

## §6. Ràng buộc ops nêu

- <ghi dạng dữ kiện>

## §7. Điều chưa biết

- [ ] <câu hỏi cho phase analyze>
- [ ] Ops nghi ngờ / gợi ý cách làm: <CỦA OPS> (chưa kiểm chứng)

## §8. Ngoài phạm vi / vấn đề phụ phát hiện

- <vấn đề phụ 1 — một câu>

## §9. Nguồn — nguyên văn

> <lời ops, không sửa chính tả>

`[GH #N]`
> <câu quyết định trong issue, nguyên văn>

## §10. Delta so với lần raise trước

- File trước: `<tên file>`
- Lần này khác: <một dòng>
```

---

## Vì sao từng slot tồn tại

| § | Vì sao cần |
|---|---|
| §1 | Nén được thành một câu mới chứng tỏ đã khoanh đúng một tính năng, không phải một cụm |
| §2 | "Khoảng trống hôm nay" là thứ phân biệt NR với BUG. Workaround thủ công cho biết mức đau thật |
| §3 | User story ép nêu **ai** và **để làm gì** — chặn kiểu mô tả chỉ có giải pháp mà không có nhu cầu |
| §4 | Nguồn yêu cầu quyết định độ ưu tiên; không phải bằng chứng lỗi |
| §5 | **Integration point là bắt buộc** — xem đầu file |
| §6 | Ràng buộc là dữ kiện, không phải chỉ thị implement |
| §7 | Agenda cho phase analyze |
| §8 | Chống scope creep |
| §9 | Arbiter khi tranh chấp câu chữ |
| §10 | Giữ mạch giữa các lần raise |

**Cấm ở form này**: chọn stack/thư viện/kiến trúc. Stack là **đầu ra** của phase analyze, không phải đầu vào — nêu sẵn thì phase sau confirm bias thay vì cân trade-off. Nếu ops tự nêu, ghi vào §7 dưới dạng gợi ý *của ops*, không phải quyết định.
