import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:telegram_client/telegram_client.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const TelegramApp());
}

class TelegramApp extends StatelessWidget {
  const TelegramApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Telegram Native Custom',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: const Color(0xFF17212B),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF242F3D),
          elevation: 0,
        ),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFF64B5F6),
          surface: Color(0xFF242F3D),
        ),
      ),
      home: const TelegramAuthOrMainScreen(),
    );
  }
}

class TelegramAuthOrMainScreen extends StatefulWidget {
  const TelegramAuthOrMainScreen({super.key});

  @override
  State<TelegramAuthOrMainScreen> createState() => _TelegramAuthOrMainScreenState();
}

class _TelegramAuthOrMainScreenState extends State<TelegramAuthOrMainScreen> {
  final Tdlib _tdlib = Tdlib();
  final int _clientId = 1;

  final int _apiId = 94575;
  final String _apiHash = 'a3406de8d171326e3c403d80a9b00a9c';

  bool _isSubmitting = false;
  bool _isAuthorized = false;
  
  String _authState = 'init';
  String _statusText = 'جاري تهيئة TDLib...';

  final TextEditingController _phoneController = TextEditingController();
  final TextEditingController _codeController = TextEditingController();

  List<Map<String, dynamic>> _chats = [];
  Timer? _timeoutTimer;

  @override
  void initState() {
    super.initState();
    _initTdlib();
  }

  @override
  void dispose() {
    _timeoutTimer?.cancel();
    super.dispose();
  }

  void _startTimeout() {
    _timeoutTimer?.cancel();
    _timeoutTimer = Timer(const Duration(seconds: 7), () {
      if (mounted && _isSubmitting) {
        setState(() {
          _isSubmitting = false;
          _statusText = 'تأخرت الاستجابة من السيرفر، يرجى المحاولة مرة أخرى.';
        });
      }
    });
  }

  Future<void> _initTdlib() async {
    try {
      _tdlib.createclient(clientId: _clientId);

      _tdlib.on(_tdlib.event_update, (UpdateTelegramClientTdlib update) {
        if (update.client_id == _clientId && update.raw is Map) {
          _handleUpdate(Map<String, dynamic>.from(update.raw));
        }
      });

      setState(() {
        _statusText = 'تم إنشاء العميل، بانتظار استجابة المكتبة...';
      });
    } catch (e) {
      setState(() {
        _statusText = 'خطأ في التهيئة: $e';
      });
    }
  }

  void _handleUpdate(Map<String, dynamic> update) {
    final type = update['@type'];

    if (type == 'error') {
      _timeoutTimer?.cancel();
      setState(() {
        _isSubmitting = false;
        _statusText = 'خطأ من تليجرام: ${update['message']}';
      });
      return;
    }

    if (type == 'updateAuthorizationState') {
      final authState = update['authorization_state'];
      if (authState != null && authState is Map) {
        final authType = authState['@type'];
        _timeoutTimer?.cancel();

        if (authType == 'authorizationStateWaitTdlibParameters') {
          setState(() {
            _authState = 'wait_params';
            _statusText = 'جاري إرسال إعدادات API...';
          });
          _sendTdlibParametersAuto();
        } else if (authType == 'authorizationStateWaitPhoneNumber') {
          setState(() {
            _authState = 'wait_phone';
            _isSubmitting = false;
            _statusText = 'جاهز: اضغط إرسال رمز التحقق';
          });
        } else if (authType == 'authorizationStateWaitCode') {
          setState(() {
            _authState = 'wait_code';
            _isSubmitting = false;
            _statusText = 'تم إرسال الكود إلى تطبيق تليجرام لديك!';
          });
        } else if (authType == 'authorizationStateReady') {
          setState(() {
            _isAuthorized = true;
            _authState = 'ready';
            _isSubmitting = false;
            _statusText = 'تم تسجيل الدخول بنجاح!';
          });
          _loadChats();
        }
      }
    }
  }

  Future<void> _sendTdlibParametersAuto() async {
    final Directory appDocDir = await getApplicationDocumentsDirectory();
    final String dbPath = "${appDocDir.path}/tdlib_db";

    await _tdlib.invoke(
      'setTdlibParameters',
      parameters: {
        'api_id': _apiId,
        'api_hash': _apiHash,
        'system_language_code': 'ar',
        'device_model': 'Android',
        'system_version': 'Android 12',
        'application_version': '1.0.0',
        'database_directory': dbPath,
        'files_directory': dbPath,
        'use_secret_chats': true,
        'use_message_database': true,
        'use_file_database': true,
      },
      clientId: _clientId,
    );
  }

  Future<void> _sendPhoneNumber() async {
    String phone = _phoneController.text.trim();

    if (phone.startsWith('+9640')) {
      phone = '+964${phone.substring(5)}';
      _phoneController.text = phone;
    }

    if (phone.isEmpty) {
      setState(() => _statusText = 'يرجى إدخال رقم الهاتف أولاً');
      return;
    }

    setState(() {
      _isSubmitting = true;
      _statusText = 'جاري إرسال رقم الهاتف...';
    });
    _startTimeout();

    await _tdlib.invoke(
      'setAuthenticationPhoneNumber',
      parameters: {
        'phone_number': phone,
      },
      clientId: _clientId,
    );
  }

  Future<void> _sendCode() async {
    final code = _codeController.text.trim();
    if (code.isEmpty) return;

    setState(() {
      _isSubmitting = true;
      _statusText = 'جاري التحقق من الرمز...';
    });
    _startTimeout();

    await _tdlib.invoke(
      'checkAuthenticationCode',
      parameters: {
        'code': code,
      },
      clientId: _clientId,
    );
  }

  Future<void> _loadChats() async {
    final res = await _tdlib.invoke(
      'getChats',
      parameters: {'limit': 30},
      clientId: _clientId,
    );

    if (res is Map && res['chat_ids'] is List) {
      final List chatIds = res['chat_ids'];
      List<Map<String, dynamic>> loadedChats = [];
      for (var id in chatIds) {
        final chatData = await _tdlib.invoke(
          'getChat',
          parameters: {'chat_id': id},
          clientId: _clientId,
        );
        if (chatData is Map) {
          loadedChats.add(Map<String, dynamic>.from(chatData));
        }
      }
      setState(() {
        _chats = loadedChats;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isAuthorized) {
      return Scaffold(
        appBar: AppBar(
          title: const Text('تليجرام الأصلي (وضع التخفي)'),
          actions: [
            IconButton(
              icon: const Icon(Icons.refresh),
              onPressed: _loadChats,
            ),
          ],
        ),
        body: _chats.isEmpty
            ? const Center(child: Text('لا توجد محادثات محملة حالياً'))
            : ListView.builder(
                itemCount: _chats.length,
                itemBuilder: (context, index) {
                  final chat = _chats[index];
                  final title = chat['title'] ?? 'محادثة ${chat['id']}';
                  return ListTile(
                    leading: const CircleAvatar(
                      backgroundColor: Color(0xFF64B5F6),
                      child: Icon(Icons.person, color: Colors.white),
                    ),
                    title: Text(title, style: const TextStyle(color: Colors.white)),
                    subtitle: Text('ID: ${chat['id']}', style: const TextStyle(color: Colors.grey)),
                  );
                },
              ),
      );
    }

    return Scaffold(
      appBar: AppBar(title: const Text('تسجيل الدخول - تليجرام')),
      body: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFF242F3D),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  const Icon(Icons.info_outline, color: Color(0xFF64B5F6), size: 20),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      _statusText,
                      style: const TextStyle(color: Colors.white70, fontSize: 13),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            if (_authState == 'wait_code') ...[
              const Text('أدخل رمز التحقق الذي وصلك على تطبيق تليجرام'),
              const SizedBox(height: 12),
              TextField(
                controller: _codeController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'رمز التحقق (Code)',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _isSubmitting ? null : _sendCode,
                style: ElevatedButton.styleFrom(minimumSize: const Size.fromHeight(48)),
                child: _isSubmitting
                    ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('تأكيد الرمز والدخول'),
              ),
            ] else ...[
              const Text('أدخل رقم الهاتف مع الرمز الدولي'),
              const SizedBox(height: 12),
              TextField(
                controller: _phoneController,
                keyboardType: TextInputType.phone,
                decoration: const InputDecoration(
                  labelText: 'رقم الهاتف',
                  hintText: '+9647700000000',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: (_isSubmitting || _authState == 'init') ? null : _sendPhoneNumber,
                style: ElevatedButton.styleFrom(minimumSize: const Size.fromHeight(48)),
                child: _isSubmitting
                    ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('إرسال رمز التحقق'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
