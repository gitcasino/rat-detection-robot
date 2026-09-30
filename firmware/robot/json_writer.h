#pragma once

/*
 * Minimal JSON writer for telemetry payloads.
 *
 * No dynamic allocation and no Arduino dependency, so it can be exercised on a
 * workstation. Overflow is fatal by design: a truncated payload would parse as
 * malformed JSON on the server, which is worse than not sending at all. The
 * writer flags the failure and the caller skips the request.
 */

#include <stddef.h>

namespace jsonw {

class Writer {
 public:
  Writer(char *buffer, size_t capacity);

  void beginObject();
  void endObject();
  void beginArray();
  void endArray();

  void key(const char *name);

  void string(const char *value);
  void boolean(bool value);
  void integer(long value);
  void unsignedInteger(unsigned long value);
  void number(double value, int decimals = 2);
  void null();

  // Convenience pairs, so payload assembly reads as data rather than calls.
  void field(const char *name, const char *value);
  void field(const char *name, bool value);
  void field(const char *name, long value);
  void field(const char *name, unsigned long value);
  void field(const char *name, double value, int decimals = 2);

  bool ok() const { return ok_; }
  size_t size() const { return length_; }
  const char *c_str() const { return buffer_; }

 private:
  void push(char value);
  void pushRaw(const char *value);
  void pushEscaped(const char *value);
  void pushUnsigned(unsigned long value);
  void separate();
  void markDirty();

  char *buffer_;
  size_t capacity_;
  size_t length_ = 0;
  bool ok_ = true;
  // Tracks whether the current container already holds an entry, which is what
  // decides if a separating comma is required.
  bool needs_comma_ = false;
  bool in_object_ = false;
  bool after_key_ = false;
};

}  // namespace jsonw
