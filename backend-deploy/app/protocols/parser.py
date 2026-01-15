"""
HJ212 Protocol Parser

This module implements the main parser for HJ 212-2017 and HJ 212-2025
environmental monitoring data transmission protocols.
"""

import re
from typing import Dict, Optional, Tuple, Any
from datetime import datetime

from .crc import verify_crc
from .enums import ProtocolVersion, FlagBits, PARAMETER_DESCRIPTIONS, PARAMETER_UNITS
from .models import ParsedData, DataSegment, ParameterValue, ParserConfig


class HJ212Parser:
    """
    Parser for HJ212 protocol messages.

    Supports both HJ 212-2017 and HJ 212-2025 versions with automatic
    version detection and appropriate parsing logic.
    """

    def __init__(self, config: Optional[ParserConfig] = None):
        """
        Initialize parser with configuration.

        Args:
            config: Parser configuration, uses defaults if not provided
        """
        self.config = config or ParserConfig()

        # Regex patterns for parsing
        self.packet_pattern = re.compile(
            rb'^##(\d{4})(.+?)([0-9A-Fa-f]{4})\r\n$',
            re.DOTALL
        )

        # Pattern for extracting key=value pairs from data segment
        self.field_pattern = re.compile(
            r'([A-Za-z]+)=([^;]*)'
        )

        # Pattern for parsing CP parameter data
        self.param_pattern = re.compile(
            r'([a-z]\d{5})-([A-Za-z]+)=([^,;]*)'
        )

    def parse(self, raw_data: bytes) -> ParsedData:
        """
        Parse HJ212 protocol message.

        Args:
            raw_data: Raw bytes received from device

        Returns:
            ParsedData object with parsed information

        Raises:
            ValueError: If packet format is invalid
            RuntimeError: If parsing fails
        """
        errors = []

        try:
            # Step 1: Validate packet structure
            packet_info = self._validate_packet_structure(raw_data)
            if not packet_info:
                raise ValueError("Invalid packet structure")

            data_len, data_segment, crc_hex = packet_info

            # Step 2: Validate CRC if enabled
            if self.config.validate_crc:
                if not verify_crc(data_segment.encode('ascii'), crc_hex):
                    if self.config.strict_mode:
                        raise ValueError(f"CRC validation failed: expected {crc_hex}")
                    errors.append(f"CRC validation failed")

            # Step 3: Parse data segment
            segment = self._parse_data_segment(data_segment)

            # Step 4: Determine protocol version
            version = self._detect_version(segment.flag)

            # Step 5: Parse CP content if present
            is_encrypted = False
            parameters = {}

            if segment.cp:
                # Extract CP content (between &&...&&)
                cp_content = self._extract_cp_content(segment.cp)

                if cp_content:
                    # Check if content is encrypted (2025 version feature)
                    if version == ProtocolVersion.HJ212_2025 and self._is_encrypted(cp_content):
                        is_encrypted = True
                        if self.config.auto_decrypt and self.config.sm4_key:
                            cp_content = self._decrypt_sm4(cp_content, self.config.sm4_key)
                        else:
                            errors.append("CP content is encrypted but no decryption key provided")

                    # Parse parameters from CP content
                    if not is_encrypted or (is_encrypted and self.config.auto_decrypt):
                        parameters = self._parse_cp_parameters(cp_content)

            # Step 6: Extract system time if present
            system_time = self._extract_system_time(segment.cp) if segment.cp else None

            # Step 7: Validate timestamp if required
            if self.config.validate_timestamp:
                if not self._validate_timestamp(segment.timestamp):
                    if self.config.strict_mode:
                        raise ValueError("Timestamp validation failed")
                    errors.append("Timestamp is outside allowed drift range")

            # Build parsed data object
            parsed = ParsedData(
                raw=raw_data,
                data_len=data_len,
                crc=crc_hex,
                segment=segment,
                parameters=parameters,
                system_time=system_time,
                version=version,
                is_encrypted=is_encrypted,
                is_valid=len(errors) == 0,
                errors=errors
            )

            return parsed

        except Exception as e:
            if self.config.strict_mode:
                raise
            # Return partial result with error information
            return ParsedData(
                raw=raw_data,
                data_len=0,
                crc="",
                segment=DataSegment(
                    qn=datetime.now().strftime("%Y%m%d%H%M%S000"),
                    st="00",
                    cn="0000",
                    mn="0" * 24,
                    flag=0
                ),
                version=ProtocolVersion.HJ212_2017,
                is_valid=False,
                errors=[str(e)]
            )

    def _validate_packet_structure(self, raw_data: bytes) -> Optional[Tuple[int, str, str]]:
        """
        Validate basic packet structure.

        Returns:
            Tuple of (data_len, data_segment, crc) or None if invalid
        """
        # Check minimum length
        if len(raw_data) < 14:  # ##0000****\r\n minimum
            return None

        # Check header and tail
        if not raw_data.startswith(b'##') or not raw_data.endswith(b'\r\n'):
            return None

        # Extract components
        match = self.packet_pattern.match(raw_data)
        if not match:
            return None

        data_len_str = match.group(1).decode('ascii')
        data_segment = match.group(2).decode('ascii')
        crc_hex = match.group(3).decode('ascii').upper()

        # Validate data length
        data_len = int(data_len_str)
        actual_len = len(data_segment)

        if data_len != actual_len:
            return None

        # Check maximum packet size
        if data_len > self.config.max_packet_size:
            return None

        return data_len, data_segment, crc_hex

    def _parse_data_segment(self, segment_str: str) -> DataSegment:
        """
        Parse the data segment into structured fields.

        Args:
            segment_str: Data segment string

        Returns:
            DataSegment object
        """
        fields = {}

        # Extract all key=value pairs
        for match in self.field_pattern.finditer(segment_str):
            key = match.group(1).upper()  # Normalize to uppercase
            value = match.group(2)
            fields[key] = value

        # Handle CP field specially (can contain semicolons)
        cp_match = re.search(r'CP=&&(.*)&&', segment_str)
        if cp_match:
            fields['CP'] = cp_match.group(1)

        # Extract required fields
        qn = fields.get('QN', datetime.now().strftime("%Y%m%d%H%M%S000"))
        st = fields.get('ST', '00')
        cn = fields.get('CN', '0000')
        pw = fields.get('PW')
        mn = fields.get('MN', '0' * 24)
        flag = int(fields.get('FLAG', fields.get('Flag', '0')))

        # Extract packet split info if present
        pnum = None
        pno = None
        if flag & FlagBits.SPLIT_BIT:
            pnum = int(fields.get('PNUM', '1'))
            pno = int(fields.get('PNO', '1'))

        return DataSegment(
            qn=qn,
            st=st,
            cn=cn,
            pw=pw,
            mn=mn,
            flag=flag,
            pnum=pnum,
            pno=pno,
            cp=fields.get('CP')
        )

    def _detect_version(self, flag: int) -> ProtocolVersion:
        """
        Detect protocol version from flag bits.

        Args:
            flag: Flag value (0-255)

        Returns:
            Detected protocol version
        """
        version_bits = (flag >> FlagBits.VERSION_START) & 0x3F

        if version_bits == 1:
            return ProtocolVersion.HJ212_2017
        elif version_bits >= 2:
            return ProtocolVersion.HJ212_2025
        else:
            # Default to 2017 for version 0 or unknown
            return ProtocolVersion.HJ212_2017

    def _extract_cp_content(self, cp_field: str) -> str:
        """
        Extract content from CP field (remove && markers if present).

        Args:
            cp_field: Raw CP field value

        Returns:
            CP content without markers
        """
        # CP field already extracted without && markers in _parse_data_segment
        return cp_field

    def _is_encrypted(self, content: str) -> bool:
        """
        Check if CP content is encrypted.

        For 2025 version, encrypted content is typically hex-encoded.

        Args:
            content: CP content string

        Returns:
            True if content appears to be encrypted
        """
        # Check if content is all hex characters (typical for encrypted data)
        # Also check length is even (hex encoded bytes)
        if len(content) % 2 != 0:
            return False

        # Check if it's hex-encoded
        try:
            bytes.fromhex(content)
            # If successful and doesn't look like normal parameter format
            if not re.search(r'[a-z]\d{5}-', content):
                return True
        except ValueError:
            pass

        return False

    def _decrypt_sm4(self, encrypted_content: str, key: str) -> str:
        """
        Decrypt SM4 encrypted content.

        This is a placeholder for SM4 decryption logic.
        Actual implementation requires SM4 library.

        Args:
            encrypted_content: Hex-encoded encrypted data
            key: SM4 key (32 hex characters)

        Returns:
            Decrypted content string
        """
        # TODO: Implement SM4 decryption
        # This requires external SM4 library (e.g., gmssl or cryptography with SM4 support)
        # For now, return as-is with a warning

        # Placeholder implementation:
        # try:
        #     from app.core.encryption import sm4_decrypt
        #     encrypted_bytes = bytes.fromhex(encrypted_content)
        #     key_bytes = bytes.fromhex(key)
        #     decrypted_bytes = sm4_decrypt(encrypted_bytes, key_bytes)
        #     return decrypted_bytes.decode('utf-8')
        # except ImportError:
        #     pass

        return encrypted_content  # Return as-is for now

    def _parse_cp_parameters(self, cp_content: str) -> Dict[str, ParameterValue]:
        """
        Parse parameter values from CP content.

        Args:
            cp_content: CP content string (decrypted if was encrypted)

        Returns:
            Dictionary of parameter code to ParameterValue
        """
        parameters = {}
        temp_params = {}

        # Parse all parameter-attribute=value pairs
        for match in self.param_pattern.finditer(cp_content):
            param_code = match.group(1).lower()  # e.g., w01001
            attribute = match.group(2)          # e.g., Rtd, Flag, Min, Max
            value = match.group(3)               # The value

            if param_code not in temp_params:
                temp_params[param_code] = {}

            # Store attribute
            temp_params[param_code][attribute.lower()] = value

        # Convert to ParameterValue objects
        for code, attrs in temp_params.items():
            param = ParameterValue(code=code)

            # Parse numeric values
            for attr_name in ['rtd', 'min', 'max', 'avg', 'cou']:
                if attr_name in attrs:
                    try:
                        setattr(param, attr_name, float(attrs[attr_name]))
                    except (ValueError, TypeError):
                        pass

            # Parse flag values
            if 'flag' in attrs:
                param.flag = attrs['flag']
            if 'eflag' in attrs:
                param.eFlag = attrs['eflag']

            parameters[code] = param

        # Also check for simple DataTime field
        datetime_match = re.search(r'DataTime=(\d{14})', cp_content)
        if datetime_match:
            # Store as a special parameter
            dt_param = ParameterValue(
                code='DataTime',
                rtd=0  # Placeholder
            )
            parameters['DataTime'] = dt_param

        return parameters

    def _extract_system_time(self, cp_content: Optional[str]) -> Optional[datetime]:
        """
        Extract system time from CP content if present.

        Args:
            cp_content: CP content string

        Returns:
            Datetime object or None
        """
        if not cp_content:
            return None

        # Look for DataTime field
        match = re.search(r'DataTime=(\d{14})', cp_content)
        if match:
            try:
                dt_str = match.group(1)
                return datetime.strptime(dt_str, "%Y%m%d%H%M%S")
            except ValueError:
                pass

        return None

    def _validate_timestamp(self, timestamp: datetime) -> bool:
        """
        Validate that timestamp is within acceptable range.

        Args:
            timestamp: Timestamp to validate

        Returns:
            True if valid, False otherwise
        """
        now = datetime.now()
        drift = abs((now - timestamp).total_seconds())
        return drift <= self.config.max_timestamp_drift

    def format_response(self, parsed_data: ParsedData, response_code: str = "9014") -> bytes:
        """
        Format a response message for the parsed data.

        Args:
            parsed_data: The parsed data to respond to
            response_code: Response command code (default 9014 for data ACK)

        Returns:
            Formatted response message as bytes
        """
        # Build response data segment
        response_qn = datetime.now().strftime("%Y%m%d%H%M%S000")
        response_segment = (
            f"QN={response_qn};"
            f"ST={parsed_data.segment.st};"
            f"CN={response_code};"
            f"PW={parsed_data.segment.pw or '123456'};"
            f"MN={parsed_data.segment.mn};"
            f"Flag={(parsed_data.segment.flag & 0xFE)};"  # Clear ACK bit
            f"CP=&&Result=1&&"
        )

        # Calculate CRC
        from .crc import crc16_to_hex, calculate_crc16
        crc = calculate_crc16(response_segment.encode('ascii'))
        crc_hex = crc16_to_hex(crc)

        # Format complete packet
        data_len = len(response_segment)
        packet = f"##{data_len:04d}{response_segment}{crc_hex}\r\n"

        return packet.encode('ascii')