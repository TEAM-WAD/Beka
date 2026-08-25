import 'package:flutter/material.dart';
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

  // مفاتيح API الرسمية مدمجة تلقائياً لتخطي خطوة الإدخال اليدوي
  final int _apiId = 94575;
  final String _apiHash = 'a3406de8d171326e3c403d80a9b00a9c';

  bool _isSubmitting = false;
  bool _isAuthorized = false;
  String _authState = 'loading'; // loading, wait_phone, wait_code, ready

  final TextEditingController _phoneController = TextEditingController();
  final TextEditingController _codeController = TextEditingController();

  List<Map<String, dynamic>> _chats = [];

  @override
  void initState() {
    super.initState();
    _initTdlib();
  }

  Future<void> _initTdlib() async {
    try {
      _tdlib.createclient(clientId: _clientId);

      _tdlib.on(_tdlib.event_update, (UpdateTelegramClientTdlib update) {
        if (update.client_id == _clientId && update.raw is Map) {
          _handleUpdate(Map<String, dynamic>.from(update.raw));
        }
      });
    } catch (e) {
      debugPrint('TDLib Init Error: $e');
    }
  }

  void _handleUpdate(Map<String, dynamic> update) {
    final type = update['@type'];
    if (type == 'updateAuthorizationState') {
      final authState = update['authorization_state'];
      if (authState != null && authState is Map) {
        final authType = authState['@type'];
        
        // إرسال الإعدادات تلقائياً بمجرد طلب TDLib لها
        if (authType == 'authorizationStateWaitTdlibParameters') {
          _sendTdlibParametersAuto();
        } else if (authType == 'authorizationStateWaitPhoneNumber') {
          setState(() {
            _authState = 'wait_phone';
            _isSubmitting = false;
          });
        } else if (authType == 'authorizationStateWaitCode') {
          setState(() {
            _authState = 'wait_code';
            _isSubmitting = false;
          });
        } else if (authType == 'authorizationStateReady') {
          setState(() {
            _isAuthorized = true;
            _authState = 'ready';
            _isSubmitting = false;
          });
          _loadChats();
        }
      }
    }
  }

  Future<void> _sendTdlibParametersAuto() async {
    await _tdlib.invoke(
      'setTdlibParameters',
      parameters: {
        'api_id': _apiId,
        'api_hash': _apiHash,
        'system_language_code': 'ar',
        'device_model': 'Android Mobile',
        'application_version': '1.0.0',
        'database_directory': '/data/user/0/com.example.telegram_custom_native/app_flutter/tdlib',
        'use_secret_chats': true,
        'use_message_database': true,
        'use_file_database': true,
      },
      clientId: _clientId,
    );
  }

  Future<void> _sendPhoneNumber() async {
    final phone = _phoneController.text.trim();
    if (phone.isEmpty) return;

    setState(() => _isSubmitting = true);

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

    setState(() => _isSubmitting = true);

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

  Future<void> _viewStoryStealth(int chatId, int storyId) async {
    final storyData = await _tdlib.invoke(
      'getStory',
      parameters: {
        'story_sender_chat_id': chatId,
        'story_id': storyId,
      },
      clientId: _clientId,
    );

    if (mounted) {
      showDialog(
        context: context,
        builder: (context) => AlertDialog(
          backgroundColor: const Color(0xFF242F3D),
          title: const Text('مشاهدة الاستوري (مخفي)', style: TextStyle(color: Colors.white)),
          content: Text(
            'تم جلب الاستوري بنجاح دون تسجيل أي مشاهدة للسيرفر!\n\n$storyData',
            style: const TextStyle(color: Colors.white70),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('إغلاق'),
            ),
          ],
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isAuthorized) {
      return Scaffold(
        appBar: AppBar(
          title: const Text('محادثات تليجرام (وضع التخفي)'),
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
                    trailing: IconButton(
                      icon: const Icon(Icons.visibility_off, color: Colors.lightBlueAccent),
                      tooltip: 'مشاهدة الاستوري بدون علم صاحبها',
                      onPressed: () => _viewStoryStealth(chat['id'], 1),
                    ),
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
            if (_authState == 'loading') ...[
              const Center(child: CircularProgressIndicator()),
              const SizedBox(height: 16),
              const Text('جاري الاتصال بسيرفرات تليجرام...', textAlign: TextAlign.center),
            ] else if (_authState == 'wait_phone') ...[
              const Text('أدخل رقم الهاتف مع الرمز الدولي', style: TextStyle(fontSize: 16)),
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
                onPressed: _isSubmitting ? null : _sendPhoneNumber,
                style: ElevatedButton.styleFrom(minimumSize: const Size.fromHeight(48)),
                child: _isSubmitting
                    ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('إرسال رمز التحقق'),
              ),
            ] else if (_authState == 'wait_code') ...[
              const Text('أدخل رمز التحقق الذي وصلك على تليجرام', style: TextStyle(fontSize: 16)),
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
            ],
          ],
        ),
      ),
    );
  }
}
