# Form — CR (change requirement)

Thứ đó **đã tồn tại và đang chạy đúng như thiết kế**, nhưng cần một hành vi khác. Nếu nó chạy sai so với chính thiết kế của nó → `form-bug.md`. Nếu chưa tồn tại → `form-nr.md`.

**Slot bắt buộc (mẫu số của `completeness`) = 9**: §1 · §2 (behavior cũ) · §3 (behavior mới) · §7 · §8 · §9 · lý do đổi · ai yêu cầu · **câu hỏi backward-compat đã nêu vào §7**.

Hai luật riêng của form này:

1. **§2 behavior cũ là BẮT BUỘC.** CR là delta của một thứ đang tồn tại. Không biết chính xác hệ thống đang làm gì thì không tính được delta — phase analyze sẽ tự giả định và đi sai đường.
2. **Backward-compat KHÔNG được tự quyết.** Đó là quyết định nghiệp vụ, không phải kỹ thuật. AI có xu hướng chọn "giữ tương thích" vì nghe an toàn, nhưng đôi khi breaking change mới là đúng. Nêu thành **câu hỏi** ở §7, để ops chốt.

Không xoá section nào. Rỗng thì in nhãn. Thứ tự cố định.

---

## Khung rỗng — copy y hệt

```markdown
---
id: <slug>
raised_at: <ISO 8601 local>
type: CR
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

# CR: <title>

## §1. Vấn đề trong một câu

<một câu duy nhất: đổi cái gì thành cái gì>

## §2. Hiện trạng — behavior CŨ (bắt buộc)

> <hệ thống hiện tại đang làm gì, mô tả chính xác>

- **Đang đúng như thiết kế?**: <có — nếu "không" thì đây là BUG, sai form>
- **Có tài liệu/spec nào quy định behavior này**: <path hoặc "không rõ">
- **Behavior liên quan phải BẢO TOÀN**: <thứ không được vỡ khi đổi>

## §3. Kỳ vọng — behavior MỚI (bắt buộc)

> <business muốn nó thành gì>

- **Lý do đổi**: <bắt buộc — pain point hoặc yêu cầu nghiệp vụ>
- **Ai yêu cầu**: <bắt buộc — ops / PM / khách / compliance>

## §4. Bằng chứng (nếu có)

- **Số liệu / ví dụ cụ thể**: <giá trị hiện tại vs giá trị mong muốn>
- **Ảnh**: `[SCREENSHOT]` <mô tả chữ những gì đọc được trong ảnh + nguồn>

## §5. Vùng code liên quan — nơi behavior CŨ đang sống

| Ops nêu / anchor | Kết quả | Nhãn |
|---|---|---|
| <hint hoặc anchor> | <path:line hoặc "không tìm thấy"> | `[VERIFIED]` / `[UNVERIFIED]` / `[LOCATED … ← anchor "<s>" trong <vùng>]` |

- **Test hiện có phủ behavior cũ** (nếu ops biết): <path>

## §6. Ràng buộc ops nêu

- <ghi dạng dữ kiện>

## §7. Điều chưa biết

- [ ] **Backward-compat**: giữ tương thích / breaking change có được chấp nhận / cần feature flag? — <ops chốt, skill KHÔNG tự chọn>
- [ ] Behavior cũ có ai/hệ nào đang phụ thuộc mà ops chưa nhắc?
- [ ] <câu hỏi khác cho phase analyze>
- [ ] Ops nghi ngờ / gợi ý: <CỦA OPS> (chưa kiểm chứng)

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
| §1 | Ép nêu **cả hai đầu** của delta trong một câu — thiếu một đầu là dấu hiệu chưa rõ |
| §2 | Không có behavior cũ thì không có delta. "Đang đúng như thiết kế?" là câu chặn phân loại sai BUG↔CR |
| §3 | Behavior mới + **lý do** + **ai yêu cầu**: CR không có người yêu cầu thì thường là ý tưởng, chưa phải yêu cầu |
| §4 | Số cụ thể (cũ vs mới) chặn kiểu mô tả định tính không kiểm chứng được |
| §5 | Vùng code ở đây = **nơi behavior CŨ đang sống**, tức điểm xuất phát cho phase đo blast radius. Khác NR (nơi gắn tính năng mới vào) |
| §6 | Ràng buộc là dữ kiện, không phải chỉ thị implement |
| §7 | Chứa câu hỏi backward-compat — xem luật 2 ở đầu file |
| §8 | Chống scope creep |
| §9 | Arbiter khi tranh chấp câu chữ |
| §10 | Giữ mạch giữa các lần raise |

**Cấm ở form này**: nêu phương án implement delta, hoặc tự chốt backward-compat. Cả hai thuộc phase sau.
