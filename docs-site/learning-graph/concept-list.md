# Concept List for Mountainash Utils Files

Total concepts: 90

## Foundation Concepts (1-10)

1. File Systems
2. Cloud Object Storage
3. URL Schemes
4. Binary Streams
5. Python Protocols
6. Runtime Checkable Protocol
7. Mixin Pattern
8. Pydantic Models
9. Decorators
10. Registry Pattern

## Storage Protocols (11-18)

11. StorageConnectionProtocol
12. StorageReadProtocol
13. StorageWriteProtocol
14. StorageListProtocol
15. StorageDeleteProtocol
16. StorageMetadataProtocol
17. StorageCopyProtocol
18. StorageDirectoryProtocol

## StorageFacade (19-30)

19. StorageFacade Class
20. Protocol Checked Dispatch
21. UnsupportedOperationError
22. Read Bytes Method
23. Read Stream Method
24. Write Bytes Method
25. Write Stream Method
26. List Files Method
27. Delete Method
28. Exists Method
29. Get Metadata Method
30. Copy Method

## Path Handling (31-40)

31. StoragePath Class
32. SchemeSpec Dataclass
33. SCHEMES Registry
34. Alias Resolution
35. Identify Scheme Method
36. Normalize Method
37. GenericSchemePath Fallback
38. Path Joining
39. UPath Integration
40. Detect Provider From Path

## Transforms (41-52)

41. StreamTransform Protocol
42. Wrap Method
43. Unwrap Method
44. Pipeline Class
45. Apply Read Direction
46. Apply Write Direction
47. Gzip Transform
48. GPG Transform
49. Suffix Transforms Map
50. Infer Pipeline Function
51. Materialize Utility
52. PairedStream Helper

## Local Backend (53-62)

53. LocalStorageBackend Class
54. LocalConnectionMixin
55. LocalReadMixin
56. LocalWriteMixin
57. LocalListMixin
58. LocalDeleteMixin
59. LocalMetadataMixin
60. LocalCopyMixin
61. LocalDirectoryMixin
62. Full Protocol Coverage Local

## S3 Backend (63-76)

63. S3StorageBackend Class
64. S3ConnectionMixin
65. S3ReadMixin
66. S3WriteMixin
67. S3ListMixin
68. S3DeleteMixin
69. S3MetadataMixin
70. S3CopyMixin
71. Boto3 Client
72. S3 Flavor Dispatch
73. AWS S3 Flavor
74. S3 Express One Zone Flavor
75. Cloudflare R2 Flavor
76. MinIO Flavor

## HTTP Backend (77-82)

77. HTTPStorageBackend Class
78. HTTP Read Support
79. HTTP Metadata Support
80. HTTP Connection Support
81. Httpx Client
82. HTTP Error Mapping

## Settings & Configuration (83-90)

83. StorageAuthBase Class
84. Provider Type Enum
85. Auth Method Enum
86. Access Type Enum
87. Per Provider Settings
88. Settings Descriptor
89. Settings Profile
90. Settings Adapters
