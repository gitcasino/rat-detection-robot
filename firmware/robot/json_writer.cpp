#include "json_writer.h"

#include <stdint.h>

namespace jsonw {

namespace {

char hex_digit(uint8_t value) {
  static const char kDigits[] = "0123456789abcdef";
  return kDigits[value & 0x0F];
}

}  // namespace

Writer::Writer(char *buffer, size_t capacity) : buffer_(buffer), capacity_(capacity) {
  if (capacity_ == 0) {
    ok_ = false;
    return;
  }
  buffer_[0] = '\0';
}

void Writer::markDirty() {
  ok_ = false;
  buffer_[0] = '\0';
  length_ = 0;
}

void Writer::push(char value) {
  if (!ok_) {
    return;
  }
  if (length_ + 1 >= capacity_) {
    markDirty();
    return;
  }
  buffer_[length_++] = value;
  buffer_[length_] = '\0';
}

void Writer::pushRaw(const char *value) {
  if (value == nullptr) {
    return;
  }
  while (*value != '\0') {
    push(*value++);
  }
}

void Writer::pushEscaped(const char *value) {
  if (value == nullptr) {
    return;
  }
  for (const char *cursor = value; *cursor != '\0'; cursor++) {
    const char character = *cursor;
    switch (character) {
      case '"':
      case '\\':
        push('\\');
        push(character);
        continue;
      case '\n':
        push('\\');
        push('n');
        continue;
      case '\r':
        push('\\');
        push('r');
        continue;
      case '\t':
        push('\\');
        push('t');
        continue;
      default:
        break;
    }
    const unsigned char raw = static_cast<unsigned char>(character);
    if (raw < 0x20) {
      push('\\');
      push('u');
      push('0');
      push('0');
      push(hex_digit(raw >> 4));
      push(hex_digit(raw));
      continue;
    }
    push(character);
  }
}

void Writer::separate() {
  if (after_key_) {
    after_key_ = false;
    return;
  }
  if (needs_comma_) {
    push(',');
  }
  needs_comma_ = true;
}

void Writer::beginObject() {
  separate();
  push('{');
  needs_comma_ = false;
  in_object_ = true;
}

void Writer::endObject() {
  push('}');
  needs_comma_ = true;
  in_object_ = false;
}

void Writer::beginArray() {
  separate();
  push('[');
  needs_comma_ = false;
  in_object_ = false;
}

void Writer::endArray() {
  push(']');
  needs_comma_ = true;
}

void Writer::key(const char *name) {
  separate();
  push('"');
  pushEscaped(name);
  push('"');
  push(':');
  after_key_ = true;
}

void Writer::string(const char *value) {
  separate();
  push('"');
  pushEscaped(value);
  push('"');
}

void Writer::boolean(bool value) {
  separate();
  pushRaw(value ? "true" : "false");
}

void Writer::integer(long value) {
  separate();
  char scratch[16];
  size_t index = sizeof(scratch);
  const bool negative = value < 0;
  unsigned long magnitude = negative ? static_cast<unsigned long>(-value)
                                     : static_cast<unsigned long>(value);
  scratch[--index] = '\0';
  do {
    scratch[--index] = static_cast<char>('0' + (magnitude % 10));
    magnitude /= 10;
  } while (magnitude > 0 && index > 1);
  if (negative) {
    scratch[--index] = '-';
  }
  pushRaw(&scratch[index]);
}

void Writer::pushUnsigned(unsigned long value) {
  char scratch[16];
  size_t index = sizeof(scratch);
  scratch[--index] = '\0';
  do {
    scratch[--index] = static_cast<char>('0' + (value % 10));
    value /= 10;
  } while (value > 0 && index > 1);
  pushRaw(&scratch[index]);
}

void Writer::unsignedInteger(unsigned long value) {
  separate();
  pushUnsigned(value);
}

void Writer::number(double value, int decimals) {
  separate();
  if (decimals < 0) {
    decimals = 0;
  }
  if (decimals > 6) {
    decimals = 6;
  }

  // Fixed-point formatting without printf float support, which several embedded
  // toolchains still do not provide.
  const bool negative = value < 0.0;
  const double magnitude = negative ? -value : value;
  double scale = 1.0;
  for (int i = 0; i < decimals; i++) {
    scale *= 10.0;
  }
  const unsigned long limit = static_cast<unsigned long>(scale);
  const unsigned long scaled = static_cast<unsigned long>(magnitude * scale + 0.5);
  const unsigned long whole = scaled / limit;
  const unsigned long fraction = scaled % limit;

  if (negative && (whole > 0 || fraction > 0)) {
    push('-');
  }
  pushUnsigned(whole);
  if (decimals > 0) {
    push('.');
    unsigned long divisor = limit / 10;
    while (divisor > 0) {
      push(static_cast<char>('0' + (fraction / divisor) % 10));
      divisor /= 10;
    }
  }
}

void Writer::null() {
  separate();
  pushRaw("null");
}

void Writer::field(const char *name, const char *value) {
  key(name);
  string(value);
}

void Writer::field(const char *name, bool value) {
  key(name);
  boolean(value);
}

void Writer::field(const char *name, long value) {
  key(name);
  integer(value);
}

void Writer::field(const char *name, unsigned long value) {
  key(name);
  unsignedInteger(value);
}

void Writer::field(const char *name, double value, int decimals) {
  key(name);
  number(value, decimals);
}

}  // namespace jsonw
