# Form — BUG

Hệ thống làm **sai so với thứ chính nó đáng ra phải làm**. Nếu tính năng đó chưa từng tồn tại → đây không phải BUG, quay lại `form-nr.md`. Nếu code khớp spec mà business muốn khác → `form-cr.md`.

**Slot bắt buộc (mẫu số của `completeness`) = 9**: §1 · §2 · §3 · §4 · §7 · §8 · §9 · môi trường · regression (từng chạy đúng chưa).

Không xoá section nào. Rỗng thì in nhãn. Thứ tự cố định.

---

## Khung rỗng — copy y hệt

```markdown
---
id: <slug>
raised_at: <ISO 8601 local>
type: BUG
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

# BUG: <title>

## §1. Vấn đề trong một câu

<một câu duy nhất, nhãn nguồn>

## §2. Hiện trạng — triệu chứng

- **Hệ thống đang làm gì**: <…>
- **Môi trường**: <local / dev / stg / prd> — <bắt buộc>
- **Tần suất**: <luôn luôn / thỉnh thoảng / một lần>
- **Regression?**: <trước đây từng chạy đúng: có / không / không rõ> — <bắt buộc>
- **Log / error nguyên văn**:
  ```
  <paste nguyên văn, không sửa>
  ```

## §3. Kỳ vọng

<hệ thống đáng ra phải làm gì, theo lời ops>

## §4. Bằng chứng & bước tái hiện

1. <bước 1>
2. <bước 2>
3. <quan sát được gì>

- **Dữ liệu đầu vào**: <giá trị cụ thể ops đưa>
- **Ảnh**: `[SCREENSHOT]` <mô tả chữ những gì đọc được trong ảnh + nguồn>

## §5. Vùng code liên quan

| Ops nêu / anchor | Kết quả | Nhãn |
|---|---|---|
| <hint hoặc anchor> | <path:line hoặc "không tìm thấy"> | `[VERIFIED]` / `[UNVERIFIED]` / `[LOCATED … ← anchor "<s>" trong <vùng>]` |

## §6. Ràng buộc ops nêu

- <ghi dạng dữ kiện: "ops nói không được đụng X">

## §7. Điều chưa biết

- [ ] <câu hỏi cho phase analyze>
- [ ] <mâu thuẫn giữa nguồn, nếu có>
- [ ] Ops nghi ngờ: <giả thuyết CỦA OPS> (chưa kiểm chứng)

## §8. Ngoài phạm vi / vấn đề phụ phát hiện

- <vấn đề phụ 1 — một câu>

## §9. Nguồn — nguyên văn

> <lời ops, không sửa chính tả, không chuẩn hoá thuật ngữ>

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
| §1 | Không nén nổi thành một câu = chưa hiểu vấn đề, hoặc đang gộp nhiều vấn đề |
| §2 | Neo của mọi phân tích sau. **Môi trường** phân biệt lỗi cấu hình với lỗi code. **Regression** là câu hỏi đắt nhất: "từng chạy đúng" thu hẹp phạm vi về các thay đổi gần đây |
| §3 | Không có kỳ vọng thì không có tiêu chí đúng-sai |
| §4 | Bug không tái hiện được thì phase sau đi mò. Giá trị đầu vào cụ thể quan trọng hơn mô tả chung |
| §5 | Có thì tiết kiệm; đã nêu là phải verify. Mỗi dòng ghi rõ anchor đã dùng |
| §6 | Ràng buộc là **dữ kiện**, không phải mệnh lệnh cho phase implement |
| §7 | Giá trị lớn nhất của file. Chính là agenda cho phase analyze |
| §8 | Chống scope creep và chống mất thông tin ops lỡ nhắc |
| §9 | Arbiter khi tranh chấp câu chữ. Nghi form diễn giải sai → đọc §9 |
| §10 | Giữ mạch giữa các lần raise, không bắt người đọc tự diff hai file |

**Cấm ở form này**: bất kỳ câu nào nói *tại sao* lỗi xảy ra. Chỉ hiện tượng, không giải thích hiện tượng.
